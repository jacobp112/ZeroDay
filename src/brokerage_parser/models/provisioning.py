import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from brokerage_parser.db import Base

class ProvisioningStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ProvisioningRequest(Base):
    __tablename__ = "provisioning_requests"

    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_name = Column(String(255), nullable=False)
    org_slug = Column(String(255), nullable=True)
    admin_email = Column(String(255), nullable=False)
    status = Column(SAEnum(ProvisioningStatus), default=ProvisioningStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    result_data = Column(JSONB, nullable=True) # Added this
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

class PendingNotification(Base):
    __tablename__ = "pending_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    template = Column(String(50), nullable=False)
    context = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent_at = Column(DateTime(timezone=True), nullable=True)
