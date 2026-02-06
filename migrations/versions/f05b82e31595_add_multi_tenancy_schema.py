"""Add Multi-Tenancy Schema

Revision ID: f05b82e31595
Revises:
Create Date: 2026-02-06 00:54:26.229038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'f05b82e31595'
down_revision: Union[str, None] = None # Base
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Organizations
    op.create_table(
        'organizations',
        sa.Column('organization_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), unique=True, nullable=False),
        sa.Column('billing_email', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 2. Tenants
    op.create_table(
        'tenants',
        sa.Column('tenant_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.organization_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_tenant_org_slug')
    )

    # 3. API Keys
    op.create_table(
        'api_keys',
        sa.Column('key_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('access_key_id', sa.String(255), unique=True, nullable=False),
        sa.Column('secret_hash', sa.String(255), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.organization_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 4. Admin Audit Log
    op.create_table(
        'admin_audit_log',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('admin_user_id', sa.String(255), nullable=False),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=True),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('reason', sa.String(1024), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # 5. Alter Jobs (Add columns nullable first)
    op.add_column('jobs', sa.Column('tenant_id', UUID(as_uuid=True), nullable=True))
    op.add_column('jobs', sa.Column('organization_id', UUID(as_uuid=True), nullable=True))

    # FKs
    op.create_foreign_key('fk_jobs_tenants', 'jobs', 'tenants', ['tenant_id'], ['tenant_id'], ondelete='RESTRICT')
    op.create_foreign_key('fk_jobs_organizations', 'jobs', 'organizations', ['organization_id'], ['organization_id'], ondelete='RESTRICT')

    # Indexes
    op.create_index('ix_jobs_tenant_id', 'jobs', ['tenant_id'])
    op.create_index('ix_jobs_organization_id', 'jobs', ['organization_id'])
    op.create_index('ix_jobs_composite_tenant', 'jobs', ['tenant_id', 'status', 'created_at'])

    # 6. Domain Tables (Documents, Accounts, Holdings, Transactions)
    op.create_table(
        'documents',
        sa.Column('document_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.organization_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('jobs.job_id', ondelete='SET NULL'), nullable=True),
        sa.Column('file_sha256', sa.String(64), nullable=False, index=True),
        sa.Column('file_s3_key', sa.String(1024), nullable=False),
        sa.Column('broker_name', sa.String(255), nullable=True),
        sa.Column('statement_date', sa.Date(), nullable=True),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    op.create_table(
        'accounts',
        sa.Column('account_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.organization_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('account_number', sa.String(255), nullable=True),
        sa.Column('account_type', sa.String(255), nullable=True),
        sa.Column('beginning_balance', sa.Numeric(18, 4), nullable=True),
        sa.Column('ending_balance', sa.Numeric(18, 4), nullable=True),
        sa.Column('currency', sa.String(10), default='GBP')
    )

    op.create_table(
        'holdings',
        sa.Column('holding_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.account_id', ondelete='CASCADE'), nullable=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.organization_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('symbol', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Numeric(18, 6), nullable=False),
        sa.Column('price', sa.Numeric(18, 6), nullable=True),
        sa.Column('market_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('cost_basis', sa.Numeric(18, 4), nullable=True),
        sa.Column('currency', sa.String(10), default='GBP'),
        sa.Column('gbp_market_value', sa.Numeric(18, 4), nullable=True),
        sa.Column('isin', sa.String(12), nullable=True),
        sa.Column('sedol', sa.String(7), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    op.create_table(
        'transactions',
        sa.Column('transaction_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.account_id', ondelete='CASCADE'), nullable=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.tenant_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.organization_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False), # Enum as string
        sa.Column('symbol', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Numeric(18, 6), nullable=True),
        sa.Column('price', sa.Numeric(18, 6), nullable=True),
        sa.Column('amount', sa.Numeric(18, 4), nullable=False),
        sa.Column('fees', sa.Numeric(18, 4), nullable=True),
        sa.Column('currency', sa.String(10), default='GBP'),
        sa.Column('gbp_amount', sa.Numeric(18, 4), nullable=True),
        sa.Column('fx_rate', sa.Numeric(18, 6), nullable=True),
        sa.Column('source_transaction_hash', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table('transactions')
    op.drop_table('holdings')
    op.drop_table('accounts')
    op.drop_table('documents')

    op.drop_column('jobs', 'organization_id')
    op.drop_column('jobs', 'tenant_id')

    op.drop_table('admin_audit_log')
    op.drop_table('api_keys')
    op.drop_table('tenants')
    op.drop_table('organizations')
