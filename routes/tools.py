"""
WandaTools — routes/tools.py
Transactions and dashboard endpoints.

Note on Document model:
  The original tools.py referenced a Document model, DocumentType,
  DocumentStatus etc. — these do not exist in main.py yet.
  Document endpoints are included here but marked clearly so you can
  add the Document model to main.py when ready. They are safe to deploy
  now — they simply return a "coming soon" response until the model exists.

Endpoints:
  POST   /api/v1/tools/transactions          — create transaction
  GET    /api/v1/tools/transactions          — list transactions (filtered)
  GET    /api/v1/tools/transactions/{id}     — get single transaction
  PUT    /api/v1/tools/transactions/{id}     — update transaction
  DELETE /api/v1/tools/transactions/{id}     — delete transaction
  GET    /api/v1/tools/dashboard/summary     — monthly summary
  GET    /api/v1/tools/dashboard/history     — multi-month history
  POST   /api/v1/tools/documents             — generate document (stub)
  GET    /api/v1/tools/documents             — list documents (stub)
  GET    /api/v1/tools/documents/{id}        — get document (stub)
  DELETE /api/v1/tools/documents/{id}        — delete document (stub)
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import get_db
from main import (
    User,
    SUPPORTED_CURRENCIES,
    DEFAULT_CURRENCY,
)
from notifications       import NotificationService
from routes.transactions import Transaction, MonthlyTransactionSummary, TransactionType
from routes.auth         import get_current_user

log = logging.getLogger("wandatools.tools")

router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])

VALID_TYPES = {"income", "expense"}


def _parse_iso_date(date_str: str) -> datetime:
    """
    Parse an ISO date string to a naive datetime object.

    Accepted formats:
      YYYY-MM-DD                  plain date (frontend date input)
      YYYY-MM-DDTHH:MM:SS         local datetime
      YYYY-MM-DDTHH:MM:SS.fffZ   JS Date.toISOString() output
      YYYY-MM-DDTHH:MM:SS+HH:MM  timezone-aware ISO 8601

    Python < 3.11 does not recognise 'Z' as a valid timezone suffix in
    datetime.fromisoformat(), so we normalise it to '+00:00' first.
    The result is stored timezone-naive (UTC assumed).
    """
    try:
        normalized = date_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid date '{date_str}' — "
                "use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
            ),
        )


# ─────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────

class TransactionCreateRequest(BaseModel):
    type:             str
    amount:           float
    category:         str
    description:      str
    transaction_date: str
    currency:         str | None = None
    notes:            str | None = None
    is_recurring:     bool       = False
    tax_deductible:   bool       = False

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_TYPES:
            raise ValueError(f"type must be 'income' or 'expense', got '{v}'")
        return v

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"amount must be greater than 0, got {v}")
        return v

    @field_validator("category")
    @classmethod
    def category_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("category cannot be empty")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description cannot be empty")
        return v


class TransactionUpdateRequest(BaseModel):
    type:             str | None   = None
    amount:           float | None = None
    category:         str | None   = None
    description:      str | None   = None
    transaction_date: str | None   = None
    currency:         str | None   = None
    notes:            str | None   = None
    is_recurring:     bool | None  = None
    tax_deductible:   bool | None  = None

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower().strip()
        if v not in VALID_TYPES:
            raise ValueError(f"type must be 'income' or 'expense', got '{v}'")
        return v

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v <= 0:
            raise ValueError(f"amount must be greater than 0, got {v}")
        return v


def _txn_dict(t: Transaction) -> dict:
    """Serialize a Transaction ORM object to a response dict."""
    return {
        "id":               t.id,
        "user_id":          t.user_id,
        "type":             t.type,
        "amount":           t.amount,
        "currency":         t.currency,
        "category":         t.category,
        "description":      t.description,
        "transaction_date": t.transaction_date.isoformat(),
        "created_at":       t.created_at.isoformat(),
        "updated_at":       t.updated_at.isoformat() if t.updated_at else None,
    }


def _rebuild_monthly_summary(db: Session, user_id: int, txn_date: datetime, currency: str) -> None:
    """
    Rebuild the monthly summary cache after any transaction change.
    Wrapped in its own try/except so a summary failure never
    blocks the transaction response.
    """
    try:
        month = txn_date.strftime("%Y-%m")
        MonthlyTransactionSummary.rebuild_for_month(
            db=db,
            user_id=user_id,
            month=month,
            currency=currency,
        )
    except Exception as exc:
        log.warning(f"Monthly summary rebuild failed (user={user_id}): {exc}")


# ─────────────────────────────────────────────────────────────
# TRANSACTIONS — CREATE
# ─────────────────────────────────────────────────────────────

@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def create_transaction(
    body:         TransactionCreateRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Create a new income or expense transaction.
    currency defaults to the user's set currency if not provided.
    transaction_date must be ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
    """
    parsed_date = _parse_iso_date(body.transaction_date)

    txn_currency = (body.currency or current_user.currency).upper()
    if txn_currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported currency '{txn_currency}'. Accepted: {', '.join(SUPPORTED_CURRENCIES)}",
        )

    try:
        txn = Transaction(
            user_id=current_user.id,
            type=body.type,
            amount=body.amount,
            currency=txn_currency,
            category=body.category,
            description=body.description,
            transaction_date=parsed_date,
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)

        # 🔔 Notify user their transaction was saved
        NotificationService.notify_transaction_created(
            db=db,
            user_id=current_user.id,
            amount=txn.amount,
            currency=current_user.currency,
            txn_type=txn.type,
            txn_id=txn.id,
        )

        # 📊 Rebuild monthly summary cache
        _rebuild_monthly_summary(db, current_user.id, txn.transaction_date, current_user.currency)

        log.info(f"✅ Transaction {txn.id} created for user {current_user.id}")
        return {**_txn_dict(txn), "message": "✅ Transaction saved!"}

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"create_transaction error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save transaction: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# TRANSACTIONS — LIST  (with filters)
# ─────────────────────────────────────────────────────────────

@router.get("/transactions")
async def list_transactions(
    current_user:     User    = Depends(get_current_user),
    db:               Session = Depends(get_db),
    skip:             int     = Query(0,    ge=0),
    limit:            int     = Query(10,   ge=1, le=100),
    transaction_type: str     = Query(None, description="Filter: income or expense"),
    category:         str     = Query(None, description="Filter by category name"),
    start_date:       str     = Query(None, description="Filter from date: YYYY-MM-DD"),
    end_date:         str     = Query(None, description="Filter to date: YYYY-MM-DD"),
):
    """
    List the authenticated user's transactions, newest first.
    Supports filtering by type, category, and date range.
    """
    try:
        query = (
            db.query(Transaction)
            .filter(
                Transaction.user_id    == current_user.id,
                Transaction.is_deleted == False,           # noqa: E712
            )
        )

        if transaction_type:
            if transaction_type.lower() not in VALID_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="transaction_type must be 'income' or 'expense'",
                )
            query = query.filter(Transaction.type == transaction_type.lower())

        if category:
            query = query.filter(Transaction.category == category)

        if start_date:
            query = query.filter(
                Transaction.transaction_date >= _parse_iso_date(start_date)
            )

        if end_date:
            query = query.filter(
                Transaction.transaction_date <= _parse_iso_date(end_date)
            )

        query = query.order_by(Transaction.transaction_date.desc())
        total = query.count()
        txns  = query.offset(skip).limit(limit).all()

        return {
            "items":       [_txn_dict(t) for t in txns],
            "total":       total,
            "page":        (skip // limit) + 1,
            "page_size":   limit,
            "total_pages": (total + limit - 1) // limit,
            "currency":    current_user.currency,
        }

    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"list_transactions error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load transactions: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# TRANSACTIONS — GET SINGLE
# ─────────────────────────────────────────────────────────────

@router.get("/transactions/{transaction_id}")
async def get_transaction(
    transaction_id: int,
    current_user:   User    = Depends(get_current_user),
    db:             Session = Depends(get_db),
):
    """Get a single transaction by ID. Only returns it if it belongs to the logged-in user."""
    txn = (
        db.query(Transaction)
        .filter(
            Transaction.id         == transaction_id,
            Transaction.user_id    == current_user.id,
            Transaction.is_deleted == False,              # noqa: E712
        )
        .first()
    )
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found or does not belong to you",
        )
    return _txn_dict(txn)


# ─────────────────────────────────────────────────────────────
# TRANSACTIONS — UPDATE
# ─────────────────────────────────────────────────────────────

@router.put("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    body:           TransactionUpdateRequest,
    current_user:   User    = Depends(get_current_user),
    db:             Session = Depends(get_db),
):
    """
    Update a transaction. Only include fields you want to change.
    You cannot change the user_id — transactions always belong to the original owner.
    """
    txn = (
        db.query(Transaction)
        .filter(
            Transaction.id         == transaction_id,
            Transaction.user_id    == current_user.id,
            Transaction.is_deleted == False,              # noqa: E712
        )
        .first()
    )
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found or does not belong to you",
        )

    try:
        # Save original date before any changes — needed for summary rebuild
        original_date = txn.transaction_date

        if body.type is not None:
            txn.type = body.type
        if body.amount is not None:
            txn.amount = body.amount
        if body.category is not None:
            txn.category = body.category.strip()
        if body.description is not None:
            txn.description = body.description.strip()
        if body.transaction_date is not None:
            txn.transaction_date = _parse_iso_date(body.transaction_date)
        if body.currency is not None:
            c = body.currency.upper()
            if c not in SUPPORTED_CURRENCIES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unsupported currency '{c}'",
                )
            txn.currency = c

        db.commit()
        db.refresh(txn)

        # 📊 Rebuild summary for original month AND new month if date changed
        _rebuild_monthly_summary(db, current_user.id, original_date, current_user.currency)
        if txn.transaction_date != original_date:
            _rebuild_monthly_summary(db, current_user.id, txn.transaction_date, current_user.currency)

        log.info(f"✏️  Transaction {transaction_id} updated by user {current_user.id}")
        return {**_txn_dict(txn), "message": "✅ Transaction updated!"}

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        log.error(f"update_transaction error (txn {transaction_id}, user {current_user.id}): {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not update transaction: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# TRANSACTIONS — DELETE
# ─────────────────────────────────────────────────────────────

@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_200_OK)
async def delete_transaction(
    transaction_id: int,
    current_user:   User    = Depends(get_current_user),
    db:             Session = Depends(get_db),
):
    """Delete a transaction. Only the owner can delete their own transactions."""
    txn = (
        db.query(Transaction)
        .filter(
            Transaction.id         == transaction_id,
            Transaction.user_id    == current_user.id,
            Transaction.is_deleted == False,              # noqa: E712
        )
        .first()
    )
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found or does not belong to you",
        )
    try:
        txn_date = txn.transaction_date

        txn.soft_delete()
        db.commit()

        # 📊 Rebuild monthly summary after deletion
        _rebuild_monthly_summary(db, current_user.id, txn_date, current_user.currency)

        log.info(f"🗑️  Transaction {transaction_id} deleted by user {current_user.id}")
        return {"message": f"✅ Transaction {transaction_id} deleted!"}

    except Exception as exc:
        db.rollback()
        log.error(f"delete_transaction error (txn {transaction_id}): {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete transaction: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# DASHBOARD — MONTHLY SUMMARY
# ─────────────────────────────────────────────────────────────

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
    month:        str     = Query(None, description="Month in YYYY-MM format. Defaults to current month."),
):
    """
    Get income, expenses, net profit and category breakdown for a specific month.
    Defaults to the current month if no month is provided.
    """
    if not month:
        month = datetime.utcnow().strftime("%Y-%m")

    try:
        year_str, month_str = month.split("-")
        year      = int(year_str)
        month_num = int(month_str)
        if not (1 <= month_num <= 12):
            raise ValueError()
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid month '{month}' — use YYYY-MM format, e.g. 2025-06",
        )

    first_day = datetime(year, month_num, 1)
    if month_num == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        last_day = datetime(year, month_num + 1, 1) - timedelta(seconds=1)

    try:
        txns = (
            db.query(Transaction)
            .filter(
                Transaction.user_id          == current_user.id,
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date <= last_day,
                Transaction.is_deleted       == False,     # noqa: E712
            )
            .all()
        )
    except Exception as exc:
        log.error(f"dashboard summary error for user {current_user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load dashboard data: {exc}",
        )

    total_income   = sum(t.amount for t in txns if t.type == TransactionType.INCOME)
    total_expenses = sum(t.amount for t in txns if t.type == TransactionType.EXPENSE)
    net_profit     = total_income - total_expenses
    margin         = (net_profit / total_income * 100) if total_income > 0 else 0.0

    income_by_category:  dict[str, float] = {}
    expense_by_category: dict[str, float] = {}
    for t in txns:
        if t.type == TransactionType.INCOME:
            income_by_category[t.category]  = income_by_category.get(t.category,  0.0) + t.amount
        else:
            expense_by_category[t.category] = expense_by_category.get(t.category, 0.0) + t.amount

    return {
        "month":                month,
        "currency":             current_user.currency,
        "total_income":         total_income,
        "total_expenses":       total_expenses,
        "net_profit":           net_profit,
        "profit_margin":        round(margin, 2),
        "transaction_count":    len(txns),
        "income_by_category":   income_by_category,
        "expense_by_category":  expense_by_category,
        "top_income_category":  (
            max(income_by_category,  key=income_by_category.get)  if income_by_category  else None
        ),
        "top_expense_category": (
            max(expense_by_category, key=expense_by_category.get) if expense_by_category else None
        ),
    }


# ─────────────────────────────────────────────────────────────
# DASHBOARD — MULTI-MONTH HISTORY
# ─────────────────────────────────────────────────────────────

@router.get("/dashboard/history")
async def get_dashboard_history(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
    months:       int     = Query(6, ge=1, le=12, description="Number of months to retrieve (1–12)"),
):
    """
    Get income, expenses, and net profit for each of the last N months.
    Returns oldest month first — ideal for charts.
    """
    summaries = []
    now = datetime.utcnow()

    for i in range(months):
        # Compute exact calendar month boundaries by stepping back i months
        month_num = now.month - i
        year      = now.year
        while month_num <= 0:
            month_num += 12
            year      -= 1

        first_day = datetime(year, month_num, 1)
        if month_num == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            last_day = datetime(year, month_num + 1, 1) - timedelta(seconds=1)

        month_str = first_day.strftime("%Y-%m")

        try:
            txns = (
                db.query(Transaction)
                .filter(
                    Transaction.user_id          == current_user.id,
                    Transaction.transaction_date >= first_day,
                    Transaction.transaction_date <= last_day,
                    Transaction.is_deleted       == False,   # noqa: E712
                )
                .all()
            )
        except Exception as exc:
            log.error(f"dashboard history error (month {month_str}): {exc}")
            txns = []

        total_income   = sum(t.amount for t in txns if t.type == TransactionType.INCOME)
        total_expenses = sum(t.amount for t in txns if t.type == TransactionType.EXPENSE)

        summaries.append({
            "month":          month_str,
            "total_income":   total_income,
            "total_expenses": total_expenses,
            "net_profit":     total_income - total_expenses,
        })

    return {
        "currency":  current_user.currency,
        "months":    months,
        "summaries": list(reversed(summaries)),   # oldest → newest for charts
    }


