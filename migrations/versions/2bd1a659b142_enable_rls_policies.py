"""Enable RLS Policies

Revision ID: 2bd1a659b142
Revises: f05b82e31595
Create Date: 2026-02-06 00:53:35.100774

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2bd1a659b142'
down_revision: Union[str, None] = 'f05b82e31595'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable RLS on Tables
    tables = [
        'organizations', 'tenants', 'api_keys', 'jobs',
        'documents', 'accounts', 'holdings', 'transactions', 'admin_audit_log'
    ]

    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE RLS makes table owner also subject to policies
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # 2. Define Policies

    # Generic Template
    def create_tenant_policy(table_name):
        op.execute(f"""
            CREATE POLICY {table_name}_tenant_isolation_select ON {table_name}
                FOR SELECT
                USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """)
        op.execute(f"""
            CREATE POLICY {table_name}_tenant_isolation_insert ON {table_name}
                FOR INSERT
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """)
        op.execute(f"""
            CREATE POLICY {table_name}_tenant_isolation_update ON {table_name}
                FOR UPDATE
                USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """)
        op.execute(f"""
            CREATE POLICY {table_name}_tenant_isolation_delete ON {table_name}
                FOR DELETE
                USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """)

    # Apply Generic (jobs, documents, accounts, holdings, transactions, api_keys)
    # api_keys: Filter by tenant_id.
    for table in ['jobs', 'documents', 'accounts', 'holdings', 'transactions', 'api_keys']:
        create_tenant_policy(table)

    # Special Cases

    # Organizations: No RLS (or view all?). Plan said "No RLS needed (or filter by organization_id)".
    # But later said "RLS is FORCE enabled using using tenant_id".
    # Organization doesn't have tenant_id. It has organization_id.
    # If we enabled RLS on organizations, we need a policy.
    # If we want it public/shared?
    # Policy: "USING (true)" (Visible to all) or specific filter?
    # Let's assume Organization is visible to all authenticated users (or at least users belonging to it).
    # But user has org_id in session.
    op.execute("""
        CREATE POLICY organizations_select ON organizations
            FOR SELECT
            USING (organization_id = current_setting('app.current_organization_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY organizations_insert ON organizations
            FOR INSERT
            WITH CHECK (true)
    """)
    op.execute("""
        CREATE POLICY organizations_update ON organizations
            FOR UPDATE
            USING (true)
            WITH CHECK (true)
    """)

    # Tenants: Filter by organization_id OR tenant_id
    op.execute("""
        CREATE POLICY tenants_select ON tenants
            FOR SELECT
            USING (
                organization_id = current_setting('app.current_organization_id', true)::uuid
                OR
                tenant_id = current_setting('app.current_tenant_id', true)::uuid
            )
    """)
    op.execute("""
        CREATE POLICY tenants_insert ON tenants
            FOR INSERT
            WITH CHECK (true)
    """)
    op.execute("""
        CREATE POLICY tenants_update ON tenants
            FOR UPDATE
            USING (true)
            WITH CHECK (true)
    """)

    # Admin Audit Log: Insert only

    # Admin Audit Log: Append Only. Select by Admin only?
    # We can use a policy that checks role or specific flag?
    # "SELECT requires admin role"
    # For now, allow Insert by anyone (audit logging), Select by None (Denied) unless Bypass.
    op.execute("""
        CREATE POLICY audit_log_insert ON admin_audit_log
            FOR INSERT
            WITH CHECK (true)
    """)

    # Revoke Update/Delete
    op.execute("REVOKE UPDATE, DELETE ON admin_audit_log FROM public")
    op.execute("REVOKE UPDATE, DELETE ON admin_audit_log FROM session_user") # If applicable
    # No Select policy -> strictly denied for normal users.

    # Create Admin Role for Bypass (if possible via migration, requires superuser)
    # op.execute("CREATE ROLE admin_user WITH LOGIN PASSWORD 'adminpass' BYPASSRLS")
    # This might fail on RDS/Managed DBs.
    # We skip role creation in migration usually.


def downgrade() -> None:
    tables = [
        'organizations', 'tenants', 'api_keys', 'jobs',
        'documents', 'accounts', 'holdings', 'transactions', 'admin_audit_log'
    ]
    for table in tables:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_delete ON {table}")
