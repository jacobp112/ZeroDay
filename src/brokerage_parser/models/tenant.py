import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint, BigInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from brokerage_parser.db import Base

class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    billing_email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenants = relationship("Tenant", back_populates="organization", cascade="all, delete-orphan") # Cascade handled by DB FK too, but ORM good too

class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="tenants")
    api_keys = relationship("ApiKey", back_populates="tenant", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uc_org_slug'),
    )

class ApiKey(Base):
    __tablename__ = "api_keys"

    key_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    access_key_id = Column(String(255), nullable=False, index=True, unique=True)
    secret_hash = Column(String(255), nullable=False) # Bcrypt hash
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False) # Redundant but useful for quick RLS
    name = Column(String(255), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="api_keys")

class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_user_id = Column(String(255), nullable=False, index=True)
    action = Column(String(255), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True) # Logical link, strictly FK might be tricky if bypassing RLS? No, FK is fine.
    # Actually, if we audit access to a tenant that gets deleted, do we want to keep the log?
    # Yes, Audit Logs should stick around. So NO FK or ON DELETE SET NULL?
    # Requirement: "Retention Policy... 7 years".
    # If we use FK RESTRICT, we can't delete Tenant until Logs are gone?
    # Or we use FK ON DELETE CASCADE? NO, logs must persist.
    # So NO FK constraint on tenant_id in Audit Log is safer for "Immutable Log" logic,
    # or referencing a logical ID.
    # I'll stick to UUID type but maybe NO ForeignKey constraint to avoid deletion blocks/cascades.
    # Or strict FK? "Foreign Keys: Enforce referential integrity".
    # If I enforce FK, I can't delete a tenant without deleting logs.
    # User said: "Cannot delete tenant with data (must archive first)".
    # So FK is fine.

    resource_id = Column(String(255), nullable=True)
    reason = Column(String(1024), nullable=False)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    # Immutability is enforced by DB REVOKE, but helpful to note here
