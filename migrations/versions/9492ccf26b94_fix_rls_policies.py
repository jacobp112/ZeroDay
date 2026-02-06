"""fix_rls_policies

Revision ID: 9492ccf26b94
Revises: 5971b00fbe99
Create Date: 2026-02-06 02:04:55.497190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9492ccf26b94'
down_revision: Union[str, None] = '5971b00fbe99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tables = ['organizations', 'tenants', 'api_keys', 'jobs', 'documents', 'accounts', 'transactions', 'holdings']

    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

        # Comprehensive Cleanup
        legacy = [
            f"{table}_tenant_isolation", f"{table}_tenant_isolation_select",
            f"{table}_tenant_isolation_mod", "api_key_access", "org_isolation", "tenants_select",
             "admin_full_access" # Drop as we will recreate it for co-existence or handle in head
        ]
        for poly in legacy:
            op.execute(f"DROP POLICY IF EXISTS {poly} ON {table}")

        if table == 'organizations':
            col, var = 'organization_id', 'app.current_organization_id'
        else:
            col, var = 'tenant_id', 'app.current_tenant_id'

        # Use CASE to prevent lazy evaluation issues with CAST to UUID
        rls_clause = f"""
        (CASE
            WHEN current_setting('app.is_admin', true) = 'true' THEN TRUE
            WHEN current_setting('app.in_auth_flow', true) = 'true' THEN TRUE
            WHEN current_setting('{var}', true) IS NOT NULL AND current_setting('{var}', true) != ''
                THEN {col} = (CASE WHEN current_setting('{var}', true) ~ '^[0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{12}}$'
                                   THEN current_setting('{var}', true)::uuid
                                   ELSE NULL END)
            ELSE FALSE
        END)
        """

        op.execute(f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
            FOR ALL
            USING ({rls_clause})
            WITH CHECK ({rls_clause})
        """)

def downgrade() -> None:
    tables = ['organizations', 'tenants', 'api_keys', 'jobs', 'documents', 'accounts', 'transactions', 'holdings']
    for table in tables:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
