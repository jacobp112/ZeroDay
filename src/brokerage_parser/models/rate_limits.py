import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, ForeignKey, DateTime, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from brokerage_parser.db import Base

class TenantRateLimit(Base):
    __tablename__ = "tenant_rate_limits"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), primary_key=True)
    jobs_per_hour = Column(Integer, default=100, nullable=False)
    api_calls_per_hour = Column(Integer, default=1000, nullable=False)
    concurrent_jobs = Column(Integer, default=5, nullable=False)
    storage_gb_limit = Column(Integer, default=100, nullable=False)
    custom_limits = Column(JSONB, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", backref="rate_limits", uselist=False)
