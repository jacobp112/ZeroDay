"""add_admin_rls

Revision ID: 5a20da6188c2
Revises: 9492ccf26b94
Create Date: 2026-02-06 02:19:43.866529

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a20da6188c2'
down_revision: Union[str, None] = '9492ccf26b94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tables = [
        'organizations', 'tenants', 'api_keys', 'jobs',
        'documents', 'accounts', 'transactions', 'holdings',
        'admin_audit_log'
    ]

    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS admin_full_access ON {table}")
        op.execute(f"""
        CREATE POLICY admin_full_access ON {table}
            FOR ALL
            USING (current_setting('app.is_admin', true) = 'true')
            WITH CHECK (current_setting('app.is_admin', true) = 'true')
        """)

def downgrade() -> None:
    tables = ['organizations', 'tenants', 'api_keys', 'jobs', 'documents', 'accounts', 'transactions', 'holdings', 'admin_audit_log']
    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS admin_full_access ON {table}")
