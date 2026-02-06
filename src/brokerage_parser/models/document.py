import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Integer, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from brokerage_parser.db import Base

class Document(Base):
    __tablename__ = "documents"

    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Multi-tenancy
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)

    # Link to Job
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.job_id", ondelete="SET NULL"), nullable=True, index=True)

    # Metadata
    file_sha256 = Column(String(64), nullable=False, index=True)
    file_s3_key = Column(String(1024), nullable=False)

    broker_name = Column(String(255), nullable=True)
    statement_date = Column(Date, nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    job = relationship("Job") # Backref?
    accounts = relationship("Account", back_populates="document", cascade="all, delete-orphan")
    holdings = relationship("Holding", back_populates="document", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="document", cascade="all, delete-orphan")
