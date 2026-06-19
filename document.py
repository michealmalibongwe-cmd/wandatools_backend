"""
Document Model
Represents generated financial reports and documents
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from db import Base


class DocumentType(str, enum.Enum):
    """Types of documents that can be generated"""
    AUDIT_REPORT = "audit_report"
    LOAN_APPLICATION = "loan_application"
    INVESTMENT_REPORT = "investment_report"
    MONTHLY_SUMMARY = "monthly_summary"
    CASH_FLOW = "cash_flow"
    TAX_SUMMARY = "tax_summary"


class DocumentStatus(str, enum.Enum):
    """Document generation status"""
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


class Document(Base):
    """
    Document model for storing generated reports
    """
    __tablename__ = "documents"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Document information
    type = Column(SQLEnum(DocumentType), nullable=False, index=True)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False, index=True)
    
    # File details
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)  # in bytes
    file_url = Column(String(500), nullable=True)  # Public URL for download
    
    # Content metadata
    period_start = Column(DateTime, nullable=True, comment="Report period start date")
    period_end = Column(DateTime, nullable=True, comment="Report period end date")
    
    # Statistics included
    total_revenue = Column(Float, nullable=True)
    total_expenses = Column(Float, nullable=True)
    net_profit = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    downloaded_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Metadata
    generated_by = Column(String(50), default="system", comment="user or system")
    error_message = Column(String(1000), nullable=True)  # If status is FAILED
    
    # Relationship
    user = relationship("User", back_populates="documents")
    
    def __repr__(self):
        return f"<Document(id={self.id}, user_id={self.user_id}, type='{self.type}', status='{self.status}')>"


class DocumentTemplate(Base):
    """
    Templates for document generation
    Stores pre-designed report templates
    """
    __tablename__ = "document_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Template info
    type = Column(SQLEnum(DocumentType), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500))
    
    # Template content
    html_template = Column(String(5000), nullable=False)
    css_styles = Column(String(2000), nullable=True)
    
    # Configuration
    include_charts = Column(String(200), nullable=True, comment="JSON: chart types to include")
    include_tables = Column(String(200), nullable=True, comment="JSON: tables to include")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<DocumentTemplate(id={self.id}, type='{self.type}')>"
