import logging
import uuid
import secrets
from sqlalchemy import text
from sqlalchemy.orm import Session
from brokerage_parser.db import SessionLocal, engine
from brokerage_parser.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

LEGACY_ORG_ID = settings.LEGACY_ORG_ID
LEGACY_TENANT_ID = settings.LEGACY_TENANT_ID

def run_migration():
    """
    Migrate existing data to multi-tenant structure.
    1. Check/Create Legacy Org and Tenant
    2. Backfill null tenant_id/org_id in jobs (and others if they existed, but only jobs exist currently)
    """
    session = SessionLocal()
    try:
        logger.info("Starting Multi-Tenancy Migration")

        # 1. Idempotency Check & Creation
        # We use raw SQL to avoid model dependency circular issues or strictness if models are updated
        # But using models is fine if we are careful. Let's use SQL for robustness.

        # Check Org
        org_exists = session.execute(
            text("SELECT 1 FROM organizations WHERE organization_id = :oid"),
            {"oid": LEGACY_ORG_ID}
        ).scalar()

        if not org_exists:
            logger.info(f"Creating Legacy Organization: {LEGACY_ORG_ID}")
            session.execute(
                text("""
                INSERT INTO organizations (organization_id, name, slug, is_active, created_at)
                VALUES (:oid, 'Legacy Organization', 'legacy-org', true, NOW())
                """),
                {"oid": LEGACY_ORG_ID}
            )
        else:
            logger.info("Legacy Organization exists.")

        # Check Tenant
        tenant_exists = session.execute(
            text("SELECT 1 FROM tenants WHERE tenant_id = :tid"),
            {"tid": LEGACY_TENANT_ID}
        ).scalar()

        if not tenant_exists:
            logger.info(f"Creating Legacy Tenant: {LEGACY_TENANT_ID}")
            session.execute(
                text("""
                INSERT INTO tenants (tenant_id, organization_id, name, slug, is_active, created_at)
                VALUES (:tid, :oid, 'Legacy Tenant', 'legacy-tenant', true, NOW())
                """),
                {"tid": LEGACY_TENANT_ID, "oid": LEGACY_ORG_ID}
            )
        else:
            logger.info("Legacy Tenant exists.")

        # 2. Backfill Jobs
        logger.info("Backfilling Jobs with Legacy Tenant...")
        result = session.execute(
            text("""
            UPDATE jobs
            SET tenant_id = :tid, organization_id = :oid
            WHERE tenant_id IS NULL OR organization_id IS NULL
            """),
            {"tid": LEGACY_TENANT_ID, "oid": LEGACY_ORG_ID}
        )
        logger.info(f"Backfilled {result.rowcount} jobs.")

        session.commit()
        logger.info("Migration completed successfully.")

    except Exception as e:
        session.rollback()
        logger.error(f"Migration Failed: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()
