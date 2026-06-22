"""
Tools Routes
Transactions, dashboard, and documents endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta
import json

from db import get_db
from models import User, Transaction, Document, MonthlyTransactionSummary, TransactionType, DocumentType, DocumentStatus
from schemas import (
    TransactionCreate, TransactionResponse, TransactionUpdate, TransactionListResponse,
    DashboardSummary, DocumentCreate, DocumentResponse, DocumentListResponse
)
from routes.auth import get_current_user

router = APIRouter(prefix="/tools", tags=["tools"])


# ═══ Transaction Endpoints ═══

@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new transaction
    
    - **type**: income, expense, or transfer
    - **amount**: Amount in ZAR
    - **category**: Category of transaction
    - **description**: Transaction description
    - **transaction_date**: Date of transaction
    """
    new_transaction = Transaction(
        user_id=current_user.id,
        type=transaction_data.type,
        amount=transaction_data.amount,
        category=transaction_data.category,
        description=transaction_data.description,
        transaction_date=transaction_data.transaction_date,
        reference_id=transaction_data.reference_id,
        recipient_or_payer=transaction_data.recipient_or_payer,
        notes=transaction_data.notes,
        is_recurring=transaction_data.is_recurring,
        tax_deductible=transaction_data.tax_deductible
    )
    
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    
    return new_transaction


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
    """
    List user's transactions with optional filters
    
    - **skip**: Number of items to skip
    - **limit**: Number of items to return
    - **transaction_type**: Filter by income/expense/transfer
    - **category**: Filter by category
    - **start_date**: Filter by start date
    - **end_date**: Filter by end date
    """
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    
    # Apply filters
    if transaction_type:
        query = query.filter(Transaction.type == transaction_type)
    if category:
        query = query.filter(Transaction.category == category)
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    
    # Order by date descending (newest first)
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


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific transaction"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return transaction


@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a transaction"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Update fields
    for field, value in transaction_update.dict(exclude_unset=True).items():
        setattr(transaction, field, value)
    
    db.commit()
    db.refresh(transaction)
    
    return transaction


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a transaction"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    db.delete(transaction)
    db.commit()


# ═══ Dashboard Endpoints ═══

@router.get("/dashboard/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    month: str = Query(None, description="Month in YYYY-MM format")
):
    """
    Get dashboard summary for a specific month
    
    If month is not provided, uses current month
    """
    # Use current month if not specified
    if not month:
        now = datetime.utcnow()
        month = now.strftime("%Y-%m")
    
    try:
        year, month_num = month.split("-")
        year, month_num = int(year), int(month_num)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Month format should be YYYY-MM"
        )
    
    # Calculate date range
    first_day = datetime(year, month_num, 1)
    if month_num == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        last_day = datetime(year, month_num + 1, 1) - timedelta(seconds=1)
    
    # Query transactions for the month
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date >= first_day,
        Transaction.transaction_date <= last_day
    ).all()
    
    # Calculate totals
    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expenses = sum(t.amount for t in transactions if t.type == "expense")
    net_profit = total_income - total_expenses
    
    # Breakdown by category
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
    """
    Get dashboard history for multiple months
    """
    summaries = []
    
    for i in range(months):
        date = datetime.utcnow() - timedelta(days=30 * i)
        month_str = date.strftime("%Y-%m")
        
        # Query each month
        first_day = datetime(date.year, date.month, 1)
        if date.month == 12:
            last_day = datetime(date.year + 1, 1, 1) - timedelta(seconds=1)
        else:
            last_day = datetime(date.year, date.month + 1, 1) - timedelta(seconds=1)
        
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
    """
    Generate a financial document/report
    
    Document types:
    - **audit_report**: Audit-ready report
    - **loan_application**: Loan application package
    - **investment_report**: Investment report
    - **monthly_summary**: Monthly summary
    - **cash_flow**: Cash flow analysis
    - **tax_summary**: Tax summary
    """
    # Create document record
    new_document = Document(
        user_id=current_user.id,
        type=doc_create.type,
        status=DocumentStatus.GENERATING,
        filename=f"{doc_create.type}_{datetime.utcnow().timestamp()}.pdf",
        period_start=doc_create.period_start,
        period_end=doc_create.period_end
    )
    
    # Get transaction data for the period
    if not doc_create.period_start:
        doc_create.period_start = datetime(datetime.utcnow().year, datetime.utcnow().month, 1)
    if not doc_create.period_end:
        doc_create.period_end = datetime.utcnow()
    
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_date >= doc_create.period_start,
        Transaction.transaction_date <= doc_create.period_end
    ).all()
    
    total_revenue = sum(t.amount for t in transactions if t.type == "income")
    total_expenses = sum(t.amount for t in transactions if t.type == "expense")
    
    new_document.total_revenue = total_revenue
    new_document.total_expenses = total_expenses
    new_document.net_profit = total_revenue - total_expenses
    new_document.status = DocumentStatus.READY
    new_document.file_url = f"/api/v1/documents/{new_document.id}/download"
    
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    
    return new_document


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """List user's documents"""
    query = db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.created_at.desc())
    
    total = query.count()
    documents = query.offset(skip).limit(limit).all()
    
    return DocumentListResponse(
        items=documents,
        total=total
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific document"""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document"""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    db.delete(document)
    db.commit()
