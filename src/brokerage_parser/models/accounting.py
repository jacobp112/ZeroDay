import uuid
from datetime import datetime, date, timezone
from sqlalchemy import Column, String, Integer, DateTime, Date, ForeignKey, Numeric, Enum as SAEnum, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from brokerage_parser.db import Base
from brokerage_parser.models.types import TransactionType, TaxWrapper, CorporateActionType

class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)

    account_number = Column(String(255), nullable=True)
    account_type = Column(String(255), nullable=True)
    beginning_balance = Column(Numeric(18, 4), nullable=True)
    ending_balance = Column(Numeric(18, 4), nullable=True)
    currency = Column(String(10), default="GBP")

    # Relationships
    document = relationship("Document", back_populates="accounts")
    holdings = relationship("Holding", back_populates="account", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")

class Holding(Base):
    __tablename__ = "holdings"

    holding_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.account_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=True, index=True) # Initially nullable if account parsing fails but position exists? Plan says FK.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)

    symbol = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(Numeric(18, 6), nullable=False)
    price = Column(Numeric(18, 6), nullable=True)
    market_value = Column(Numeric(18, 4), nullable=True)
    cost_basis = Column(Numeric(18, 4), nullable=True)
    currency = Column(String(10), default="GBP")

    # UK Extensions
    gbp_market_value = Column(Numeric(18, 4), nullable=True)
    isin = Column(String(12), nullable=True)
    sedol = Column(String(7), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="holdings")
    account = relationship("Account", back_populates="holdings")

class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.account_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.organization_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)

    date = Column(Date, nullable=False)
    type = Column(SAEnum(TransactionType), nullable=False)
    symbol = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    quantity = Column(Numeric(18, 6), nullable=True)
    price = Column(Numeric(18, 6), nullable=True)
    amount = Column(Numeric(18, 4), nullable=False)
    fees = Column(Numeric(18, 4), nullable=True)

    currency = Column(String(10), default="GBP")
    gbp_amount = Column(Numeric(18, 4), nullable=True)
    fx_rate = Column(Numeric(18, 6), nullable=True)

    source_transaction_hash = Column(String(255), nullable=True) # Deterministic ID from logic

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")

# TaxLot could be here too if persisted, typically calculated on fly but user might want persistence.
# Plan didn't explicitly ask for TaxLot table in "3. Create New Relational Tables" section.
# It listed Documents, Accounts, Holdings, Transactions.
# So I'll skip persisting TaxLots for now unless asked.
