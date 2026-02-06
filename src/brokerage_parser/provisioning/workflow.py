import logging
import uuid
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from brokerage_parser.db import SessionLocal
from brokerage_parser.models.tenant import Organization, Tenant, ApiKey
from brokerage_parser.models.provisioning import ProvisioningRequest, ProvisioningStatus, PendingNotification
from brokerage_parser.core.security import get_password_hash
from brokerage_parser.notifications.email import send_welcome_email
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ProvisioningWorkflow:
    """
    Orchestrates the provisioning of a new tenant.
    Ensures atomicity: either all DB resources are created, or none.
    Handles email notification with fallback.
    """

    def __init__(self, db: Session):
        self.db = db

    def provision_tenant(self, request_id: uuid.UUID) -> bool:
        """
        Executes the provisioning workflow for a given request.
        """
        # 1. Fetch Request
        req = self.db.query(ProvisioningRequest).get(request_id)
        if not req:
            logger.error(f"Provisioning request {request_id} not found")
            return False

        if req.status != ProvisioningStatus.PENDING:
            logger.warning(f"Request {request_id} is not PENDING (status: {req.status})")
            return False

        logger.info(f"Starting provisioning for {req.org_name}")
        req.status = ProvisioningStatus.IN_PROGRESS
        req.started_at = datetime.now(timezone.utc)
        self.db.commit()

        try:
            # Start Nested Transaction (Savepoint) if needed, but we are in a session.
            # We will just commit at the end. If error, rollback.
            # Note: The request status update above was committed.
            # We want to rollback resources but keep request as FAILED.

            # 2. Create Organization
            # Check slug uniqueness first?
            slug = req.org_slug
            if self.db.query(Organization).filter(Organization.slug == slug).first():
                raise ValueError(f"Organization slug '{slug}' already exists")

            org = Organization(
                name=req.org_name,
                slug=slug,
                billing_email=req.admin_email,
                is_active=True
            )
            self.db.add(org)
            self.db.flush() # Get ID

            # 3. Create Tenant
            tenant = Tenant(
                organization_id=org.organization_id,
                name=f"{req.org_name} Default",
                slug="default",
                is_active=True
            )
            self.db.add(tenant)
            self.db.flush()

            # Set Context so RLS allows ApiKey insertion
            # The Generic Policy requires tenant_id = app.current_tenant_id
            self.db.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(tenant.tenant_id)}
            )
            self.db.execute(
                text("SELECT set_config('app.current_organization_id', :oid, true)"),
                {"oid": str(org.organization_id)}
            )

            # 4. Create Initial API Key
            access_key_id = f"pk_{secrets.token_hex(8)}"
            secret_key = secrets.token_urlsafe(32)
            secret_hash = get_password_hash(secret_key)

            api_key = ApiKey(
                access_key_id=access_key_id,
                secret_hash=secret_hash,
                tenant_id=tenant.tenant_id,
                organization_id=org.organization_id,
                name="Default Admin Key",
                is_active=True
            )
            self.db.add(api_key)

            # 5. Commit Resources
            self.db.commit()

            # 6. Send Notification (Post-Commit)
            # We don't want to rollback creation if email fails, just log it.
            try:
                send_welcome_email(req.admin_email, org.name, access_key_id, secret_key)

            except Exception as e:
                logger.error(f"Failed to send email: {e}")
                self._create_pending_notification(req.admin_email, org.name, access_key_id, secret_key)

            # 7. Update Request Status
            req.status = ProvisioningStatus.COMPLETED
            req.completed_at = datetime.now(timezone.utc)
            req.result_data = {
                "organization_id": str(org.organization_id),
                "tenant_id": str(tenant.tenant_id),
                "access_key_id": access_key_id
                # Do not store secret_key in result_data permanently ideally,
                # but for initial display it might be needed if email fails.
            }
            self.db.commit()
            logger.info(f"Provisioning completed for {req.org_name}")
            return True

        except Exception as e:
            logger.exception(f"Provisioning failed for {request_id}")
            self.db.rollback()
            # Mark request as FAILED (needs new transaction/refresh since we rolled back)
            # We need to re-fetch req because it was detached/expired on rollback
            req = self.db.query(ProvisioningRequest).get(request_id)
            if req:
                req.status = ProvisioningStatus.FAILED
                req.error_message = str(e)
                req.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            return False

    def _create_pending_notification(self, email: str, org_name: str, access_key: str, secret_key: str):
        """
        Fallback: Store notification in DB.
        """
        try:
             # Re-fetch or use db session
             note = PendingNotification(
                 recipient=email,
                 subject="Welcome to ParseFin",
                 template="welcome_email",
                 context={
                     "org_name": org_name,
                     "access_key": access_key,
                     "secret_key": secret_key,
                     "login_url": "https://portal.parsefin.com/login"
                 }
             )
             self.db.add(note)
             self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save pending notification: {e}")
