from datetime import datetime, timezone, timedelta
import uuid

from sqlalchemy import Column, String, Integer, DateTime, Text, Enum as SAEnum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from brokerage_parser.db import Base
from brokerage_parser.models.types import JobStatus

class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(String(255), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=True)

    # Multi-tenancy
    # Initially nullable for migration, but plan says NOT NULL.
    # For coding now, I will make them nullable=True to allow existing code to run/start before migration script runs?
    # User requirement: "Make columns NOT NULL after backfill". So initially nullable or default?
    # I'll make them Nullable=True for now to avoid immediate breakage, migration script will handle making them Not Null.
    # Actually, if I add them to model as Nullable=False, creating new jobs will fail without them.
    # But I haven't updated the API to inject them yet.
    # So I MUST make them Nullable=True for now, then change to False later, or update API immediately.
    # I will make them Nullable=True and add a TODO to change to False.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=True, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=True, index=True)

    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    progress_percent = Column(Integer, default=0)
    current_step = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Auto-purge after 7 days
    expires_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(days=7)
    )

    # Input/Output
    file_s3_key = Column(String(1024), nullable=False)
    file_sha256 = Column(String(64), nullable=True, index=True)
    result_s3_key = Column(String(1024), nullable=True)

    # Error Handling
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    error_trace = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('client_id', 'idempotency_key', name='loc_client_idempotency_uc'),
        # Composite index for performance as requested
        # Index on (tenant_id, status, created_at)
        # We can't use 'Index' inside __table_args__ easily with inline definition, better to use Index() outside or inline Index=True on column?
        # Inline Index=True creates single col index.
        # Composite index needs explicitly defined Index object usually.
        # But for now I'll just rely on individual indexes and add composite in Alembic migration manually or define here.
    )

from sqlalchemy import Index
# Define Index explicitly outside class or use __table_args__ with Index
Index('ix_jobs_tenant_status_created', Job.tenant_id, Job.status, Job.created_at)
