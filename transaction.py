"""
Transaction Model
Represents financial transactions (income/expenses) for users
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from db import Base


class TransactionType(str, enum.Enum):
    """Transaction types"""
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class TransactionCategory(str, enum.Enum):
    """Transaction categories"""
    SALES = "Sales"
    SERVICES = "Services"
    RENT = "Rent"
    SALARIES = "Salaries"
    STOCK = "Stock"
    MARKETING = "Marketing"
    UTILITIES = "Utilities"
    EQUIPMENT = "Equipment"
    TRAVEL = "Travel"
    MEALS = "Meals"
    INSURANCE = "Insurance"
    TAX = "Tax"
    OTHER = "Other"


class Transaction(Base):
    """
    Transaction model for tracking income and expenses
    """
    __tablename__ = "transactions"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Transaction details
    type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    amount = Column(Float, nullable=False)  # Amount in Rands
    category = Column(
        String(100),
        nullable=False,
        index=True,
        comment="e.g., Sales, Services, Rent, Salaries, Stock, Marketing, Utilities, Other"
    )
    description = Column(String(500), nullable=False)
    
    # Reference information
    reference_id = Column(String(100), nullable=True, comment="Invoice/Receipt number")
    recipient_or_payer = Column(String(255), nullable=True)
    
    # Dates
    transaction_date = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    notes = Column(Text, nullable=True)
    is_recurring = Column(String(20), nullable=True, comment="monthly, quarterly, yearly, etc.")
    tax_deductible = Column(String(50), nullable=True, comment="Yes/No/Partial")
    
    # Relationship
    user = relationship("User", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, user_id={self.user_id}, type='{self.type}', amount={self.amount})>"


class MonthlyTransactionSummary(Base):
    """
    Cache table for monthly summaries (performance optimization)
    Stores pre-calculated monthly totals
    """
    __tablename__ = "monthly_transaction_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Month (format: YYYY-MM)
    month = Column(String(10), nullable=False, index=True)
    
    # Calculated totals
    total_income = Column(Float, default=0.0)
    total_expenses = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    transaction_count = Column(Integer, default=0)
    
    # Breakdown by category (JSON string)
    income_by_category = Column(String(2000), nullable=True)
    expense_by_category = Column(String(2000), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<MonthlySummary(user_id={self.user_id}, month='{self.month}', profit={self.net_profit})>"
