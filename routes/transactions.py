"""
WandaTools — routes/transactions.py
Location: routes/ folder

Contains:
  - TransactionType, TransactionCategory, RecurringInterval enums
  - Transaction model
  - MonthlyTransactionSummary model

These models are imported into main.py AFTER Base is defined:
    from routes.transactions import Transaction, MonthlyTransactionSummary
"""

import enum
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SQLEnum,
    Float, ForeignKey, Index, Integer, JSON,
    String, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship, Session

from main import Base, DEFAULT_CURRENCY, SUPPORTED_CURRENCIES

log = logging.getLogger("wandatools.transactions")


# ─────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────

class TransactionType(str, enum.Enum):
    INCOME   = "income"
    EXPENSE  = "expense"
    TRANSFER = "transfer"


class TransactionCategory(str, enum.Enum):
    # Income
    SALES       = "Sales"
    SERVICES    = "Services"
    GRANTS      = "Grants"
    INVESTMENTS = "Investments"
    RENTAL_IN   = "Rental Income"
    OTHER_IN    = "Other Income"
    # Expense
    RENT         = "Rent"
    SALARIES     = "Salaries"
    STOCK        = "Stock"
    MARKETING    = "Marketing"
    UTILITIES    = "Utilities"
    EQUIPMENT    = "Equipment"
    TRAVEL       = "Travel"
    MEALS        = "Meals & Entertainment"
    INSURANCE    = "Insurance"
    TAX          = "Tax"
    MAINTENANCE  = "Maintenance & Repairs"
    PROFESSIONAL = "Professional Fees"
    BANK_CHARGES = "Bank Charges"
    OTHER        = "Other"


class RecurringInterval(str, enum.Enum):
    DAILY     = "daily"
    WEEKLY    = "weekly"
    MONTHLY   = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY  = "annually"


# ─────────────────────────────────────────────────────────────
# TRANSACTION MODEL
# ─────────────────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    type     = Column(SQLEnum(TransactionType), nullable=False, index=True)
    amount   = Column(Float,      nullable=False)
    currency = Column(String(10), nullable=False, default=DEFAULT_CURRENCY)
    category = Column(String(100), nullable=False, index=True)
    description      = Column(String(500), nullable=False)
    reference_id     = Column(String(100), nullable=True)
    recipient_or_payer = Column(String(255), nullable=True)

    transaction_date = Column(DateTime, nullable=False, index=True)
    created_at       = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    notes              = Column(Text,    nullable=True)
    is_recurring       = Column(Boolean, nullable=False, default=False)
    recurring_interval = Column(SQLEnum(RecurringInterval), nullable=True)
    tax_deductible     = Column(Boolean, nullable=False, default=False)

    is_deleted = Column(Boolean,  nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="transactions")

    __table_args__ = (
        Index("ix_txn_user_date",     "user_id", "transaction_date"),
        Index("ix_txn_user_type",     "user_id", "type"),
        Index("ix_txn_user_category", "user_id", "category"),
    )

    def __repr__(self) -> str:
        return (f"<Transaction(id={self.id}, user_id={self.user_id}, "
                f"type='{self.type}', amount={self.amount} {self.currency})>")

    @property
    def is_income(self) -> bool:
        return self.type == TransactionType.INCOME

    @property
    def is_expense(self) -> bool:
        return self.type == TransactionType.EXPENSE

    @property
    def formatted_amount(self) -> str:
        return f"{self.currency} {self.amount:,.2f}"

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "user_id":             self.user_id,
            "type":                self.type,
            "amount":              self.amount,
            "currency":            self.currency,
            "formatted_amount":    self.formatted_amount,
            "category":            self.category,
            "description":         self.description,
            "reference_id":        self.reference_id,
            "recipient_or_payer":  self.recipient_or_payer,
            "transaction_date":    self.transaction_date.isoformat(),
            "notes":               self.notes,
            "is_recurring":        self.is_recurring,
            "recurring_interval":  self.recurring_interval,
            "tax_deductible":      self.tax_deductible,
            "created_at":          self.created_at.isoformat(),
            "updated_at":          self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────
# MONTHLY TRANSACTION SUMMARY MODEL
# ─────────────────────────────────────────────────────────────

class MonthlyTransactionSummary(Base):
    __tablename__ = "monthly_transaction_summaries"

    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    month    = Column(String(7),  nullable=False, index=True)
    currency = Column(String(10), nullable=False, default=DEFAULT_CURRENCY)

    total_income      = Column(Float,   nullable=False, default=0.0)
    total_expenses    = Column(Float,   nullable=False, default=0.0)
    net_profit        = Column(Float,   nullable=False, default=0.0)
    profit_margin     = Column(Float,   nullable=False, default=0.0)
    transaction_count = Column(Integer, nullable=False, default=0)
    income_count      = Column(Integer, nullable=False, default=0)
    expense_count     = Column(Integer, nullable=False, default=0)

    income_by_category  = Column(JSON, nullable=True)
    expense_by_category = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="monthly_summaries")

    __table_args__ = (
        UniqueConstraint("user_id", "month", name="uq_monthly_summary_user_month"),
    )

    def __repr__(self) -> str:
        return (f"<MonthlyTransactionSummary("
                f"user_id={self.user_id}, month='{self.month}', profit={self.net_profit})>")

    def to_dict(self) -> dict:
        return {
            "month":               self.month,
            "currency":            self.currency,
            "total_income":        self.total_income,
            "total_expenses":      self.total_expenses,
            "net_profit":          self.net_profit,
            "profit_margin":       round(self.profit_margin, 2),
            "transaction_count":   self.transaction_count,
            "income_count":        self.income_count,
            "expense_count":       self.expense_count,
            "income_by_category":  self.income_by_category  or {},
            "expense_by_category": self.expense_by_category or {},
        }

    @classmethod
    def rebuild_for_month(cls, db: Session, user_id: int,
                          month: str, currency: str = DEFAULT_CURRENCY):
        from datetime import timedelta
        year, month_num = int(month[:4]), int(month[5:7])
        first_day = datetime(year, month_num, 1)
        if month_num == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            last_day = datetime(year, month_num + 1, 1) - timedelta(seconds=1)

        txns = (
            db.query(Transaction)
            .filter(
                Transaction.user_id          == user_id,
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date <= last_day,
                Transaction.is_deleted       == False,    # noqa: E712
            )
            .all()
        )

        income_txns  = [t for t in txns if t.type == TransactionType.INCOME]
        expense_txns = [t for t in txns if t.type == TransactionType.EXPENSE]

        total_income   = sum(t.amount for t in income_txns)
        total_expenses = sum(t.amount for t in expense_txns)
        net_profit     = total_income - total_expenses
        profit_margin  = (net_profit / total_income * 100) if total_income > 0 else 0.0

        income_by_cat:  dict = {}
        expense_by_cat: dict = {}
        for t in income_txns:
            income_by_cat[t.category]  = income_by_cat.get(t.category, 0.0)  + t.amount
        for t in expense_txns:
            expense_by_cat[t.category] = expense_by_cat.get(t.category, 0.0) + t.amount

        summary = db.query(cls).filter(cls.user_id == user_id, cls.month == month).first()

        if summary:
            summary.total_income      = total_income
            summary.total_expenses    = total_expenses
            summary.net_profit        = net_profit
            summary.profit_margin     = profit_margin
            summary.transaction_count = len(txns)
            summary.income_count      = len(income_txns)
            summary.expense_count     = len(expense_txns)
            summary.income_by_category  = income_by_cat
            summary.expense_by_category = expense_by_cat
            summary.currency          = currency
        else:
            summary = cls(
                user_id=user_id, month=month, currency=currency,
                total_income=total_income, total_expenses=total_expenses,
                net_profit=net_profit, profit_margin=profit_margin,
                transaction_count=len(txns), income_count=len(income_txns),
                expense_count=len(expense_txns),
                income_by_category=income_by_cat,
                expense_by_category=expense_by_cat,
            )
            db.add(summary)

        db.commit()
        db.refresh(summary)
        log.info(f"📊 Monthly summary rebuilt: user={user_id} month={month}")
        return summary