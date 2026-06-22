"""
WandaTools — routes/tools.py
Transactions, dashboard, and documents endpoints.
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from db import get_db
from models import User, Transaction, Document, DocumentStatus
from schemas import (
    TransactionCreate, TransactionResponse, TransactionUpdate, TransactionListResponse,
    DashboardSummary, DocumentCreate, DocumentResponse, DocumentListResponse
)
from routes.auth import get_current_user

log = logging.getLogger("wandatools.tools")

router = APIRouter(prefix="/tools", tags=["Tools"])


# ═══ Transaction Endpoints ═══

@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new transaction for the authenticated user."""
    try:
        new_transaction = Transaction(
            user_id=current_user.id,
            **transaction_data.dict()
        )
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)
        log.info(f"✅ Transaction created: {new_transaction.id} for user {current_user.id}")
        return new_transaction
    except Exception as exc:
        db.rollback()
        log.error(f"❌ Transaction creation failed for user {current_user.id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not create transaction: {exc}")


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    transaction_type: str = Query(None),
    category: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None)
):
    """List user's transactions with optional filters."""
    try:
        query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

        if transaction_type:
            query = query.filter(Transaction.type == transaction_type)
        if category:
            query = query.filter(Transaction.category == category)
        if start_date:
            query = query.filter(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.filter(Transaction.transaction_date <= end_date)

        query = query.order_by(Transaction.transaction_date.desc())
        total = query.count()
        transactions = query.offset(skip).limit(limit).all()

        return TransactionListResponse(
            items=transactions,
            total=total,
            page=skip // limit + 1,
            page_size=limit,
            total_pages=(total + limit - 1) // limit
        )
    except Exception as exc:
        log.error(f"❌ Failed to list transactions for user {current_user.id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not list transactions: {exc}")


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific transaction."""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return transaction


@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a transaction."""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    try:
        for field, value in transaction_update.dict(exclude_unset=True).items():
            setattr(transaction, field, value)

        db.commit()
        db.refresh(transaction)
        log.info(f"✏️ Transaction updated: {transaction.id} for user {current_user.id}")
        return transaction
    except Exception as exc:
        db.rollback()
        log.error(f"❌ Failed to update transaction {transaction_id} for user {current_user.id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not update transaction: {exc}")


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a transaction."""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    try:
        db.delete(transaction)
        db.commit()
        log.info(f"🗑️ Transaction deleted: {transaction.id} for user {current_user.id}")
    except Exception as exc:
        db.rollback()
        log.error(f"❌ Failed to delete transaction {transaction_id} for user {current_user.id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Could not delete transaction: {exc}")


# ═══ Dashboard Endpoints ═══

@router.get("/dashboard/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    month: str = Query(None, description="Month in YYYY-MM format")
):
    """Get dashboard summary for a specific month."""
    if not month:
        now = datetime.utcnow()
        month = now.strftime("%Y-%m")

    try:
        year, month_num = map(int, month.split("-"))
    except:
        raise HTTPException(status_code=400, detail="Month format should be YYYY-MM")

    first_day = datetime(year, month_num, 1)
    last_day = datetime(year + (month_num // 12), (month_num % 12) + 1, 1) - timedelta(seconds=1)

    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date >= first_day,
        Transaction.transaction_date <= last_day
    ).all()

    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expenses = sum(t.amount for t in transactions if t.type == "expense")
    net_profit = total_income - total_expenses

    income_by_category = {}
    expense_by_category = {}
    for t in transactions:
        if t.type == "income":
            income_by_category[t.category] = income_by_category.get(t.category, 0) + t.amount
        else:
            expense_by_category[t.category] = expense_by_category.get(t.category, 0) + t.amount

    return DashboardSummary(
        total_income=total_income,
        total_expenses=total_expenses,
        net_profit=net_profit,
        transaction_count=len(transactions),
        month=month,
        income_by_category=income_by_category,
        expense_by_category=expense_by_category
    )


@router.get("/dashboard/history")
async def get_dashboard_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    months: int = Query(6, ge=1, le=12, description="Number of months to retrieve")
):
    """Get dashboard history for multiple months."""
    summaries = []
    for i in range(months):
        date = datetime.utcnow() - timedelta(days=30 * i)
        month_str = date.strftime("%Y-%m")

        first_day = datetime(date.year, date.month, 1)
        last_day = datetime(date.year + (date.month // 12), (date.month % 12) + 1, 1) - timedelta(seconds=1)

        transactions = db.query(Transaction).filter(
            Transaction.user_id == current_user.id,
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date <= last_day
        ).all()

        total_income = sum(t.amount for t in transactions if t.type == "income")
        total_expenses = sum(t.amount for t in transactions if t.type == "expense")

        summaries.append({
            "month": month_str,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": total_income - total_expenses
        })

    return {"summaries": list(reversed(summaries))}


# ═══ Document Endpoints ═══

@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def generate_document(
    doc_create: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a financial document/report."""
    try:
        new_document = Document(
            user_id=current_user.id,
            type=doc_create.type,
            status=DocumentStatus.GENERATING,
            filename=f"{doc_create.type}_{datetime.utcnow().timestamp()}.pdf",
            period_start=doc_create.period_start or datetime(datetime.utcnow().