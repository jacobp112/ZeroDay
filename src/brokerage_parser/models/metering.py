import uuid
from datetime import datetime, timezone, date
from enum import Enum
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, BigInteger, Date, DECIMAL, UniqueConstraint, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from brokerage_parser.db import Base

class UsageEventType(str, Enum):
    JOB_SUBMITTED = "JOB_SUBMITTED"
    API_CALL = "API_CALL"
    STORAGE_USED = "STORAGE_USED"
    COMPUTE_SECONDS = "COMPUTE_SECONDS"

class UsageEvent(Base):
    __tablename__ = "usage_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(SAEnum(UsageEventType), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True) # e.g. job_id
    quantity = Column(DECIMAL(20, 4), nullable=False) # e.g. bytes, seconds
    metadata_ = Column("metadata", JSONB, nullable=True) # "metadata" is reserved in SA Base? typically ok as column name if different from metadata attribute. safest to quote or use name argument.
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    aggregated_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", backref="usage_events")

class UsageRecord(Base):
    __tablename__ = "usage_records"

    record_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    jobs_count = Column(Integer, default=0)
    api_calls_count = Column(Integer, default=0)
    storage_bytes = Column(BigInteger, default=0)
    compute_seconds = Column(DECIMAL(20, 4), default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", backref="usage_records")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'date', name='uc_tenant_date_usage'),
    )
