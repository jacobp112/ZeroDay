import functools
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Callable
from fastapi import Request, Depends
from sqlalchemy.orm import Session

from brokerage_parser.db import get_db, SessionLocal
from brokerage_parser.models.tenant import AdminAuditLog
from brokerage_parser.auth.admin import get_current_admin, AdminUser

logger = logging.getLogger("audit")

def log_admin_action(
    action: str,
    entity_type: str,
    get_entity_id: Optional[Callable] = None,
    required_reason: bool = False
):
    """
    Decorator to log admin actions.
    Should be placed AFTER auth dependency.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute the function first
            # We need to capture the response or input depending on requirement.
            # Usually we log strictly on success.

            # Extract dependencies
            request: Request = kwargs.get("request")
            db: Session = kwargs.get("db")
            current_admin: AdminUser = kwargs.get("current_user")

            # If dependencies are not found in kwargs (FastAPI injects them, but kwargs might not have them if not explicit?)
            # FastAPI passes dependencies as kwargs if they are arguments of the path operation function.
            # We need to ensure path operation has `request`, `db`, `current_user`.

            if not request or not db or not current_admin:
                # Fallback or error?
                # Probably error in development, but safe pass in prod?
                logger.error("Audit Log Failed: Missing dependencies in endpoint signature.")
                return await func(*args, **kwargs)

            # Check if reason is required (e.g. for delete)
            # We assume reason is in the body or query?
            # Ideally expected in the Pydantic model.

            response = await func(*args, **kwargs)

            try:
                # Determine entity_id
                entity_id = None
                if get_entity_id:
                    entity_id = get_entity_id(response, kwargs)

                # Create Audit Log
                # We need a fresh session or reuse existing?
                # Reuse existing is fine if we commit.
                # Or use background task? Background task is better for latency.

                # Extract reason if present in body (need to parse again? or pass via context)
                # For now simple audit:

                log_entry = AdminAuditLog(
                    admin_user_id=str(current_admin.email), # Using email as ID for human readability? Or ID?
                    action=action,
                    tenant_id=None, # Extract if specific to tenant
                    resource_id=str(entity_id) if entity_id else None,
                    reason="API Action", # TODO: Extract real reason
                    ip_address=request.client.host,
                    timestamp=datetime.now(timezone.utc)
                )
                db.add(log_entry)
                db.commit()

            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")

            return response
        return wrapper
    return decorator

# Simple helper for manual logging inside endpoints (Preferred for flexibility)
def create_audit_log(
    db: Session,
    admin_email: str,
    action: str,
    ip_address: str,
    resource_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    reason: str = "Manual Action",
    details: Optional[dict] = None
):
    log = AdminAuditLog(
        admin_user_id=admin_email,
        action=action,
        tenant_id=tenant_id,
        resource_id=resource_id,
        reason=reason,
        ip_address=ip_address,
        timestamp=datetime.now(timezone.utc)
        # details=json.dumps(details) if details else None # AuditLog model doesn't have details column yet?
        # Model check: id, admin_user_id, action, tenant_id, resource_id, reason, ip_address, timestamp.
    )
    db.add(log)
    db.commit()
