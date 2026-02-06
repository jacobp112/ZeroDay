"""rename provisioning columns fixed

Revision ID: 8389b01af5b6
Revises: c540300a7dab
Create Date: 2026-02-06 17:11:43.534344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8389b01af5b6'
down_revision: Union[str, None] = 'c540300a7dab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # admin_audit_log
    # op.create_index(op.f('ix_admin_audit_log_admin_user_id'), 'admin_audit_log', ['admin_user_id'], unique=False)
    # op.create_index(op.f('ix_admin_audit_log_tenant_id'), 'admin_audit_log', ['tenant_id'], unique=False)
    # op.create_index(op.f('ix_admin_audit_log_timestamp'), 'admin_audit_log', ['timestamp'], unique=False)

    # Check if column needs update to nullable
    op.alter_column('admin_audit_log', 'tenant_id', existing_type=postgresql.UUID(), nullable=True)

    # pending_notifications
    op.add_column('pending_notifications', sa.Column('recipient', sa.String(length=255), nullable=False))
    op.add_column('pending_notifications', sa.Column('subject', sa.String(length=255), nullable=False))
    op.add_column('pending_notifications', sa.Column('template', sa.String(length=50), nullable=False))
    op.add_column('pending_notifications', sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False))

    # Drop constraint if exists
    try:
        op.drop_constraint('pending_notifications_tenant_id_fkey', 'pending_notifications', type_='foreignkey')
    except:
        pass

    op.drop_column('pending_notifications', 'tenant_id')
    op.drop_column('pending_notifications', 'notification_type')
    op.drop_column('pending_notifications', 'payload')

    # provisioning_requests
    op.add_column('provisioning_requests', sa.Column('org_name', sa.String(length=255), nullable=False))
    op.add_column('provisioning_requests', sa.Column('org_slug', sa.String(length=255), nullable=True))
    op.add_column('provisioning_requests', sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.drop_column('provisioning_requests', 'billing_email')
    op.drop_column('provisioning_requests', 'tenant_slug')
    op.drop_column('provisioning_requests', 'organization_name')
    op.drop_column('provisioning_requests', 'tenant_name')
    op.drop_column('provisioning_requests', 'rate_limits')
    op.drop_column('provisioning_requests', 'organization_slug')


def downgrade() -> None:
    # Reverse provisioning_requests
    op.add_column('provisioning_requests', sa.Column('organization_slug', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    op.add_column('provisioning_requests', sa.Column('rate_limits', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column('provisioning_requests', sa.Column('tenant_name', sa.VARCHAR(length=255), autoincrement=False, nullable=False))
    op.add_column('provisioning_requests', sa.Column('organization_name', sa.VARCHAR(length=255), autoincrement=False, nullable=False))
    op.add_column('provisioning_requests', sa.Column('tenant_slug', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    op.add_column('provisioning_requests', sa.Column('billing_email', sa.VARCHAR(length=255), autoincrement=False, nullable=False))
    op.drop_column('provisioning_requests', 'result_data')
    op.drop_column('provisioning_requests', 'org_slug')
    op.drop_column('provisioning_requests', 'org_name')

    # Reverse pending_notifications
    op.add_column('pending_notifications', sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False))
    op.add_column('pending_notifications', sa.Column('notification_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False))
    op.add_column('pending_notifications', sa.Column('tenant_id', sa.UUID(), autoincrement=False, nullable=True))
    op.create_foreign_key('pending_notifications_tenant_id_fkey', 'pending_notifications', 'tenants', ['tenant_id'], ['tenant_id'], ondelete='CASCADE')
    op.drop_column('pending_notifications', 'context')
    op.drop_column('pending_notifications', 'template')
    op.drop_column('pending_notifications', 'subject')
    op.drop_column('pending_notifications', 'recipient')

    # Reverse admin_audit_log
    op.alter_column('admin_audit_log', 'tenant_id', existing_type=postgresql.UUID(), nullable=False)
    # op.drop_index(op.f('ix_admin_audit_log_timestamp'), table_name='admin_audit_log')
    # op.drop_index(op.f('ix_admin_audit_log_tenant_id'), table_name='admin_audit_log')
    # op.drop_index(op.f('ix_admin_audit_log_admin_user_id'), table_name='admin_audit_log')
