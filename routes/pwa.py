"""
WandaTools — routes/pwa.py
PWA support: manifest, delta sync, offline snapshot, push subscriptions, analytics.

Endpoints (all under /api/v1/pwa):
  GET    /vapid-public-key      — VAPID public key for pushManager.subscribe() (public)
  GET    /manifest              — API version + cache strategy hints (public)
  GET    /sync                  — Delta sync: data changed since last_sync (auth)
  GET    /offline-data          — Lightweight full snapshot for offline cache (auth)
  POST   /push/subscribe        — Register a Web Push subscription (auth)
  DELETE /push/unsubscribe      — Remove a push subscription (auth)
  POST   /push/test             — Send a test push to the caller's devices (auth)
  POST   /analytics             — Log a service-worker or PWA lifecycle event
  GET    /analytics/summary     — Aggregate PWA adoption metrics (auth)

Push notification setup (set these on Railway):
  VAPID_PUBLIC_KEY              Base64url-encoded VAPID public key
  VAPID_PRIVATE_KEY             Base64url-encoded VAPID private key
  VAPID_CLAIMS_EMAIL            Contact email for VAPID claims (e.g. admin@wandatools.com)

Generate VAPID keys (run once):
  from pywebpush import Vapid
  v = Vapid()
  v.generate_keys()
  print("Public:", v.public_key_urlsafe)
  print("Private:", v.private_key_urlsafe)
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db
from main import User, SUPPORTED_CURRENCIES, DEFAULT_CURRENCY
from notifications import Notification, NotificationStatus
from routes.auth import get_current_user
from routes.transactions import Transaction

log = logging.getLogger("wandatools.pwa")

router = APIRouter(prefix="/api/v1/pwa", tags=["PWA"])

VAPID_PRIVATE_KEY    = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY     = os.getenv("VAPID_PUBLIC_KEY",  "")
VAPID_CLAIMS_EMAIL   = os.getenv("VAPID_CLAIMS_EMAIL", "admin@wandatools.com")

API_VERSION     = "2.1.0"
SCHEMA_VERSION  = "2026-06-30"


# ─────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────

class PushSubscribeKeys(BaseModel):
    p256dh: str
    auth:   str


class PushSubscribeRequest(BaseModel):
    """Accepts the browser's native PushSubscription.toJSON() format."""
    endpoint:       str
    expirationTime: Optional[float] = None
    keys:           PushSubscribeKeys
    user_agent:     Optional[str]   = None


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class AnalyticsEventRequest(BaseModel):
    event_type: str                     # sw_install, pwa_install, offline_access, …
    data:       Optional[dict] = None   # arbitrary event payload


class SyncItem(BaseModel):
    type:              str                # "transaction" | "settings"
    client_id:         Optional[str] = None   # client UUID → stored as reference_id
    action:            str = "create"         # "create" | "update" | "delete"
    client_updated_at: Optional[str] = None   # ISO timestamp for conflict detection
    data:              dict


class OfflineSyncRequest(BaseModel):
    items:     list[SyncItem]
    last_sync: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _serialize_notification(n: Notification) -> dict:
    return {
        "id":          n.id,
        "type":        n.type,
        "status":      n.status,
        "title":       n.title,
        "message":     n.message,
        "action_url":  n.action_url,
        "action_text": n.action_text,
        "is_important": n.is_important,
        "created_at":  n.created_at.isoformat() + "Z",
        "read_at":     (n.read_at.isoformat() + "Z") if n.read_at else None,
    }


def _send_push(endpoint: str, p256dh: str, auth_key: str,
               title: str, body: str, data: dict | None = None) -> bool:
    """
    Send a single Web Push notification using VAPID (pywebpush 2.x).
    Returns True on success, False on any failure — never raises.
    """
    if not VAPID_PRIVATE_KEY:
        log.warning("VAPID_PRIVATE_KEY not set — push not sent")
        return False
    try:
        from pywebpush import WebPushException, webpush

        payload = json.dumps({
            "title": title,
            "body":  body,
            "data":  data or {},
            "icon":  "/icons/icon-192x192.png",
            "badge": "/icons/badge-96x96.png",
        })
        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": p256dh, "auth": auth_key},
            },
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{VAPID_CLAIMS_EMAIL}"},
            content_encoding="aes128gcm",
        )
        log.info(f"Push sent OK → {endpoint[:50]}…")
        return True
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else "no-response"
        body_text   = (exc.response.text[:300] if exc.response is not None else "") or ""
        log.error(f"WebPush HTTP {status_code} → {endpoint[:40]}…: {body_text}")
        return False
    except Exception as exc:
        log.error(f"Push send error → {endpoint[:40]}…: {exc}")
        return False


# ─────────────────────────────────────────────────────────────
# 0. VAPID PUBLIC KEY — public, no auth required
# ─────────────────────────────────────────────────────────────

@router.get("/vapid-public-key")
async def vapid_public_key():
    """Return the VAPID public key so the browser can call pushManager.subscribe()."""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications not configured — set VAPID_PUBLIC_KEY on Railway.",
        )
    return {"publicKey": VAPID_PUBLIC_KEY}


# ─────────────────────────────────────────────────────────────
# 1. MANIFEST — public, cached
# ─────────────────────────────────────────────────────────────

@router.get("/manifest")
async def pwa_manifest():
    """
    Return API version, schema version, endpoint catalogue, and cache-hint TTLs
    so the service worker and offline layer know exactly what to cache and for how long.
    """
    return JSONResponse(
        content={
            "api_version":    API_VERSION,
            "schema_version": SCHEMA_VERSION,
            "push_public_key": VAPID_PUBLIC_KEY or None,
            "cache_strategy": {
                "offline_snapshot_ttl_seconds": 300,      # /pwa/offline-data
                "transaction_list_ttl_seconds":  60,      # /tools/transactions
                "dashboard_ttl_seconds":         120,     # /tools/dashboard/*
                "profile_ttl_seconds":           600,     # /auth/me
                "manifest_ttl_seconds":          3600,    # this endpoint
            },
            "sync_endpoints": [
                "GET /api/v1/pwa/sync",
                "GET /api/v1/pwa/offline-data",
            ],
            "endpoints": {
                "auth":         "/api/v1/auth",
                "tools":        "/api/v1/tools",
                "transactions": "/api/v1/tools/transactions",
                "dashboard":    "/api/v1/tools/dashboard/summary",
                "wandaai":      "/api/v1/wandaai",
                "notifications": "/api/v1/users/notifications",
                "sync":         "/api/v1/pwa/sync",
                "offline_data": "/api/v1/pwa/offline-data",
                "push_subscribe": "/api/v1/pwa/push/subscribe",
                "analytics":    "/api/v1/pwa/analytics",
            },
        },
        headers={"Cache-Control": "public, max-age=3600, stale-while-revalidate=86400"},
    )


# ─────────────────────────────────────────────────────────────
# 2. DELTA SYNC — returns only what changed since last_sync
# ─────────────────────────────────────────────────────────────

@router.get("/sync")
async def delta_sync(
    since: Optional[str] = Query(
        None,
        description="ISO 8601 datetime of last successful sync (e.g. 2026-06-01T12:00:00Z). "
                    "Omit to receive the last 30 days.",
    ),
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Delta sync endpoint — returns transactions, notifications, and profile
    that changed since `since`. Clients save `server_time` and pass it back
    on the next call to get only incremental changes.

    Conflict resolution strategy: server timestamp wins.
    The client should always accept server data as authoritative for the
    same `updated_at` timestamp; local-only drafts with no server ID are
    queued and submitted via the normal POST endpoints when online.
    """
    server_time = datetime.utcnow()

    if since:
        try:
            since_dt = datetime.fromisoformat(
                since.strip().replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'since' value — use ISO 8601 format: 2026-01-15T10:30:00Z",
            )
    else:
        since_dt = server_time - timedelta(days=30)

    # All transactions touched since `since_dt` (includes soft-deletes)
    changed_txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id  == current_user.id,
            Transaction.updated_at >= since_dt,
        )
        .order_by(Transaction.updated_at.asc())
        .limit(500)
        .all()
    )

    active_txns = [t for t in changed_txns if not t.is_deleted]
    deleted_ids = [t.id for t in changed_txns if t.is_deleted]

    # New notifications since `since_dt`
    new_notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id   == current_user.id,
            Notification.created_at >= since_dt,
        )
        .order_by(Notification.created_at.asc())
        .limit(100)
        .all()
    )

    unread_count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == current_user.id,
            Notification.status  == NotificationStatus.UNREAD,
        )
        .scalar() or 0
    )

    response_data = {
        "server_time": server_time.isoformat() + "Z",
        "since":       since_dt.isoformat() + "Z",
        "profile": {
            "id":            current_user.id,
            "name":          current_user.name,
            "email":         current_user.email,
            "currency":      current_user.currency,
            "timezone":      current_user.timezone,
            "business_type": current_user.business_type,
        },
        "transactions": {
            "updated":     [t.to_dict() for t in active_txns],
            "deleted_ids": deleted_ids,
            "count":       len(active_txns),
        },
        "notifications": {
            "new":          [_serialize_notification(n) for n in new_notifications],
            "unread_count": unread_count,
            "count":        len(new_notifications),
        },
    }

    log.info(
        f"🔄 Sync: user={current_user.id} since={since_dt.date()} "
        f"txns={len(active_txns)} deleted={len(deleted_ids)} notifs={len(new_notifications)}"
    )

    return JSONResponse(
        content=response_data,
        headers={"Cache-Control": "private, no-store"},
    )


# ─────────────────────────────────────────────────────────────
# 3. OFFLINE SNAPSHOT — cacheable for 5 min
# ─────────────────────────────────────────────────────────────

@router.get("/offline-data")
async def offline_snapshot(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Return a complete lightweight snapshot of the user's data suitable for
    pre-caching in IndexedDB. The service worker calls this on install/activate
    so dashboards load instantly even when offline.

    Includes:
      - Full user profile
      - Last 100 transactions (active only)
      - Current month and previous month summaries
      - Last 20 unread notifications
    """
    from routes.transactions import MonthlyTransactionSummary

    now          = datetime.utcnow()
    curr_month   = now.strftime("%Y-%m")
    prev_month   = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    recent_txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id  == current_user.id,
            Transaction.is_deleted == False,        # noqa: E712
        )
        .order_by(Transaction.transaction_date.desc())
        .limit(100)
        .all()
    )

    monthly_summaries = (
        db.query(MonthlyTransactionSummary)
        .filter(
            MonthlyTransactionSummary.user_id == current_user.id,
            MonthlyTransactionSummary.month.in_([curr_month, prev_month]),
        )
        .all()
    )

    unread_notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.status  == NotificationStatus.UNREAD,
        )
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )

    response_data = {
        "generated_at": now.isoformat() + "Z",
        "profile": {
            "id":            current_user.id,
            "name":          current_user.name,
            "email":         current_user.email,
            "currency":      current_user.currency,
            "timezone":      current_user.timezone,
            "business_type": current_user.business_type,
            "created_at":    current_user.created_at.isoformat(),
        },
        "transactions":  [t.to_dict() for t in recent_txns],
        "monthly_summaries": [s.to_dict() for s in monthly_summaries],
        "notifications": [_serialize_notification(n) for n in unread_notifications],
    }

    log.info(
        f"📦 Offline snapshot: user={current_user.id} "
        f"txns={len(recent_txns)} summaries={len(monthly_summaries)}"
    )

    return JSONResponse(
        content=response_data,
        headers={"Cache-Control": "private, max-age=300, stale-while-revalidate=600"},
    )


# ─────────────────────────────────────────────────────────────
# 4. PUSH — subscribe / unsubscribe / test
# ─────────────────────────────────────────────────────────────

@router.post("/push/subscribe", status_code=status.HTTP_201_CREATED)
async def push_subscribe(
    body:         PushSubscribeRequest,
    request:      Request,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Register a Web Push subscription for the current user.
    If the endpoint is already stored, update its keys (handles key rotation).
    """
    from main import PushSubscription

    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == body.endpoint)
        .first()
    )

    if existing:
        existing.p256dh     = body.keys.p256dh
        existing.auth       = body.keys.auth
        existing.user_agent = body.user_agent or request.headers.get("User-Agent", "")
        existing.last_used  = datetime.utcnow()
        db.commit()
        log.info(f"Push subscription updated: user={current_user.id}")
        return {"message": "Push subscription updated.", "subscription_id": existing.id}

    sub = PushSubscription(
        user_id    = current_user.id,
        endpoint   = body.endpoint,
        p256dh     = body.keys.p256dh,
        auth       = body.keys.auth,
        user_agent = body.user_agent or request.headers.get("User-Agent", ""),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    log.info(f"🔔 Push subscription registered: user={current_user.id} id={sub.id}")
    return {"message": "Push subscription registered.", "subscription_id": sub.id}


@router.delete("/push/unsubscribe", status_code=status.HTTP_200_OK)
async def push_unsubscribe(
    body:         PushUnsubscribeRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Remove a push subscription by endpoint URL."""
    from main import PushSubscription

    deleted = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.endpoint == body.endpoint,
            PushSubscription.user_id  == current_user.id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()

    if deleted:
        log.info(f"🔕 Push subscription removed: user={current_user.id}")
        return {"message": "Push subscription removed."}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Subscription not found or does not belong to this account.",
    )


@router.post("/push/test")
async def push_test(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Send a test push notification to all of the caller's registered devices."""
    from main import PushSubscription

    subscriptions = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id)
        .all()
    )

    if not subscriptions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No push subscriptions registered. Subscribe first from a browser.",
        )

    results = []
    for sub in subscriptions:
        ok = _send_push(
            endpoint  = sub.endpoint,
            p256dh    = sub.p256dh,
            auth_key  = sub.auth,
            title     = "WandaTools — test notification 🎉",
            body      = "Push notifications are working on this device!",
            data      = {"type": "test"},
        )
        if ok:
            sub.last_used = datetime.utcnow()
        results.append({"endpoint_prefix": sub.endpoint[:40] + "…", "sent": ok})

    db.commit()
    sent_count = sum(1 for r in results if r["sent"])
    return {
        "message": f"Test push sent to {sent_count}/{len(subscriptions)} device(s).",
        "results": results,
    }


# ─────────────────────────────────────────────────────────────
# 5. OFFLINE BATCH SYNC — client pushes queued items to server
# ─────────────────────────────────────────────────────────────

def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        ).replace(tzinfo=None)
    except ValueError:
        return None


def _sync_transaction_item(
    item: SyncItem,
    user: User,
    db: Session,
    affected_months: set,
) -> dict:
    from routes.transactions import Transaction, TransactionType, RecurringInterval

    data   = item.data
    action = item.action.lower()

    if action in ("create", "update"):
        if not data.get("type") or data.get("amount") is None or not data.get("description"):
            raise ValueError("transaction requires: type, amount, description")

    existing = None
    if item.client_id:
        existing = (
            db.query(Transaction)
            .filter(
                Transaction.user_id      == user.id,
                Transaction.reference_id == item.client_id,
            )
            .first()
        )

    if action == "delete":
        if existing and not existing.is_deleted:
            existing.soft_delete()
            db.commit()
            affected_months.add(existing.transaction_date.strftime("%Y-%m"))
        return {"status": "synced"}

    if action == "create" and existing:
        return {"status": "skipped"}   # already landed — idempotent

    txn_date = _parse_dt(data.get("transaction_date")) or datetime.utcnow()

    if action == "update" and existing:
        client_upd = _parse_dt(item.client_updated_at)
        if client_upd and existing.updated_at and existing.updated_at > client_upd:
            return {
                "status": "conflict",
                "conflict": {
                    "client_id":      item.client_id,
                    "type":           "transaction",
                    "resolution":     "server_wins",
                    "server_version": existing.to_dict(),
                },
            }
        existing.type               = TransactionType(data["type"])
        existing.amount             = float(data["amount"])
        existing.currency           = data.get("currency", user.currency)
        existing.category           = data.get("category", "Other")
        existing.description        = data["description"]
        existing.transaction_date   = txn_date
        existing.notes              = data.get("notes")
        existing.is_recurring       = bool(data.get("is_recurring", False))
        existing.tax_deductible     = bool(data.get("tax_deductible", False))
        existing.recipient_or_payer = data.get("recipient_or_payer")
        if data.get("recurring_interval"):
            existing.recurring_interval = RecurringInterval(data["recurring_interval"])
        existing.updated_at = datetime.utcnow()
        db.commit()
        affected_months.add(txn_date.strftime("%Y-%m"))
        return {"status": "synced"}

    # Create new transaction
    from routes.transactions import Transaction as Txn, TransactionType as TT, RecurringInterval as RI
    txn = Txn(
        user_id             = user.id,
        type                = TT(data["type"]),
        amount              = float(data["amount"]),
        currency            = data.get("currency", user.currency),
        category            = data.get("category", "Other"),
        description         = data["description"],
        reference_id        = item.client_id,
        transaction_date    = txn_date,
        notes               = data.get("notes"),
        is_recurring        = bool(data.get("is_recurring", False)),
        tax_deductible      = bool(data.get("tax_deductible", False)),
        recipient_or_payer  = data.get("recipient_or_payer"),
        recurring_interval  = RI(data["recurring_interval"])
                              if data.get("recurring_interval") else None,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    affected_months.add(txn_date.strftime("%Y-%m"))
    return {"status": "synced"}


def _sync_settings_item(item: SyncItem, user: User, db: Session) -> dict:
    data    = item.data
    changed = False
    for field in ("name", "timezone", "business_type"):
        if data.get(field):
            setattr(user, field, str(data[field]).strip())
            changed = True
    if data.get("currency"):
        c = str(data["currency"]).upper()
        if c in SUPPORTED_CURRENCIES:
            user.currency = c
            changed = True
    if changed:
        db.commit()
    return {"status": "synced"}


@router.post("/sync")
async def offline_push_sync(
    body:         OfflineSyncRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Accept a batch of items queued offline and write them to the database.

    Idempotent: duplicate creates with the same client_id are skipped.
    Server always wins on conflicts (safest for financial data).
    Monthly summaries are rebuilt for all affected months after the batch.

    Request example:
        POST /api/v1/pwa/sync
        Authorization: Bearer <token>
        {
          "last_sync": "2026-06-29T08:00:00Z",
          "items": [
            {
              "type": "transaction",
              "client_id": "offline-uuid-1234",
              "action": "create",
              "client_updated_at": "2026-06-29T09:00:00Z",
              "data": {
                "type": "income", "amount": 500.00, "currency": "E",
                "category": "Sales", "description": "Cash sale",
                "transaction_date": "2026-06-29T09:00:00Z"
              }
            },
            {
              "type": "settings",
              "action": "create",
              "data": { "currency": "E", "timezone": "Africa/Johannesburg" }
            }
          ]
        }

    Response:
        {
          "status": "synced",
          "server_time": "2026-06-30T10:00:00Z",
          "synced_count": 2,
          "skipped_count": 0,
          "conflicts": [],
          "errors": []
        }
    """
    from routes.transactions import MonthlyTransactionSummary

    server_time     = datetime.utcnow()
    synced_count    = 0
    skipped_count   = 0
    conflicts: list = []
    errors:    list = []
    affected_months: set = set()

    for item in body.items:
        try:
            if item.type == "transaction":
                result = _sync_transaction_item(item, current_user, db, affected_months)
            elif item.type == "settings":
                result = _sync_settings_item(item, current_user, db)
            else:
                errors.append({"client_id": item.client_id, "error": f"unknown type: {item.type!r}"})
                continue

            if result["status"] == "synced":
                synced_count += 1
            elif result["status"] == "skipped":
                skipped_count += 1
            elif result["status"] == "conflict":
                conflicts.append(result["conflict"])

        except Exception as exc:
            db.rollback()
            log.error(f"Sync item error client_id={item.client_id}: {exc}")
            errors.append({"client_id": item.client_id, "error": str(exc)})

    for month in affected_months:
        try:
            MonthlyTransactionSummary.rebuild_for_month(
                db, current_user.id, month, current_user.currency
            )
        except Exception as exc:
            log.error(f"Monthly rebuild failed month={month}: {exc}")

    log.info(
        f"Offline sync: user={current_user.id} "
        f"synced={synced_count} skipped={skipped_count} "
        f"conflicts={len(conflicts)} errors={len(errors)}"
    )
    return {
        "status":        "synced",
        "server_time":   server_time.isoformat() + "Z",
        "synced_count":  synced_count,
        "skipped_count": skipped_count,
        "conflicts":     conflicts,
        "errors":        errors,
    }


# ─────────────────────────────────────────────────────────────
# 6. ANALYTICS — log and aggregate PWA / SW events
# ─────────────────────────────────────────────────────────────

VALID_EVENT_TYPES = {
    "sw_install",
    "sw_activate",
    "sw_fetch_hit",
    "sw_fetch_miss",
    "pwa_install",
    "pwa_launch_standalone",
    "offline_access",
    "sync_complete",
    "sync_fail",
    "push_received",
    "push_clicked",
    "background_sync",
}


@router.post("/analytics", status_code=status.HTTP_202_ACCEPTED)
async def log_pwa_event(
    body:    AnalyticsEventRequest,
    request: Request,
    # auth is optional — SW events fire before the user logs in
    authorization: Optional[str] = None,
    db:      Session = Depends(get_db),
):
    """
    Log a service-worker or PWA lifecycle event.
    Authentication is optional: unauthenticated install/activate events are
    stored with user_id=NULL so we can count anonymous PWA installs.
    """
    from main import PwaEvent

    if body.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown event_type '{body.event_type}'. Valid: {sorted(VALID_EVENT_TYPES)}",
        )

    user_id: Optional[int] = None
    if authorization and authorization.startswith("Bearer "):
        try:
            from main import decode_access_token
            payload = decode_access_token(authorization[7:])
            user_id = int(payload["sub"])
        except Exception:
            pass  # anonymous event — that's fine

    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    ua = request.headers.get("User-Agent", "")

    db.add(PwaEvent(
        user_id    = user_id,
        event_type = body.event_type,
        data       = body.data,
        ip_address = ip[:45] if ip else None,
        user_agent = ua[:500],
    ))
    db.commit()

    log.info(f"📊 PWA event: {body.event_type} user={user_id}")
    return {"accepted": True, "event_type": body.event_type}


@router.get("/analytics/summary")
async def analytics_summary(
    days:         int     = Query(30, ge=1, le=365, description="Look-back window in days"),
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Aggregate PWA adoption and service-worker metrics for the last N days.
    Returns event counts by type, daily install trend, and push subscription count.
    """
    from main import PushSubscription, PwaEvent

    since_dt = datetime.utcnow() - timedelta(days=days)

    # Count events by type
    event_counts = (
        db.query(PwaEvent.event_type, func.count(PwaEvent.id).label("count"))
        .filter(PwaEvent.created_at >= since_dt)
        .group_by(PwaEvent.event_type)
        .all()
    )

    # Total push subscriptions (all time)
    total_push_subs = db.query(func.count(PushSubscription.id)).scalar() or 0

    # User's own push subscriptions
    my_push_subs = (
        db.query(func.count(PushSubscription.id))
        .filter(PushSubscription.user_id == current_user.id)
        .scalar() or 0
    )

    # Unique users who used PWA standalone in window
    standalone_users = (
        db.query(func.count(func.distinct(PwaEvent.user_id)))
        .filter(
            PwaEvent.event_type == "pwa_launch_standalone",
            PwaEvent.created_at >= since_dt,
            PwaEvent.user_id    != None,        # noqa: E711
        )
        .scalar() or 0
    )

    return {
        "window_days":           days,
        "since":                 since_dt.isoformat() + "Z",
        "event_counts":          {row.event_type: row.count for row in event_counts},
        "total_push_subscriptions": total_push_subs,
        "my_push_subscriptions": my_push_subs,
        "standalone_users_in_window": standalone_users,
        "push_vapid_configured": bool(VAPID_PRIVATE_KEY),
    }
