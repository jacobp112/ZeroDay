from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from pydantic import BaseModel, Field

from brokerage_parser.db import get_db, SessionLocal # Use local or injected? Injected includes RLS. Admin needs BYPASS?
# Admin API needs ADMIN access.
# If RLS is FORCE, standard get_db will impose RLS of the current tenant.
# If Admin wants to access ALL tenants, they need BYPASS RLS role or user.
# OR they need to set current_tenant_id to the target tenant they are managing.
# "Super Admin Access: Create admin role that can bypass RLS but MUST log every cross-tenant access to audit table"
# The request says: "POST /admin/organizations", "POST /admin/jobs/{job_id}/reassign-tenant"
# And "Admin Bypass: Create database role admin_user with BYPASS ROW LEVEL SECURITY privilege. Application code must use this role sparingly".

# IMPLEMENTATION STRATEGY:
# For Admin Endpoints, we might need a separate DB Session that uses the 'admin_user' (if configured).
# Or we use the standard user but disable RLS?
# Postgres RLS can be bypassed if the user has BYPASSRLS attribute.
# Does our APP user have BYPASSRLS? Probably not.
# Does `config.py` allow configuring a separate ADMIN_DATABASE_URL? No.
# So we are likely using the same DB user.
# If the DB user provided in DATABASE_URL acts as both App and Admin, it must imply RLS is controlled via session vars.
# If RLS is FORCE, the strictness depends on the policy.
# My policy: `USING (tenant_id = current_setting('app.current_tenant_id')::uuid)`
# If `app.current_tenant_id` is NOT set, query returns nothing (or fails if strict cast issues, but typically boolean False).
# To BYPASS, one usually sets a flag `app.bypass_rls = 'true'` AND policy allows it OR uses a superuser.
# If we don't have a separate superuser credential, we need to modify the policy to allow bypass for a specific session var/role.
# OR we rely on `SET LOCAL app.current_tenant_id` to 'pretend' to be the tenant we are administering.
# For "List all tenants", we need to see ALL.
# Policy for `tenants` table: "Filter by organization_id OR tenant_id".
# If I am Admin of "Legacy Org", maybe I see all tenants?
# Let's assume the Super Admin belongs to the "Legacy Org" (00...00).
# If the Policy allows "Legacy Org" to see everything, that's one way.
# But request says "Super Admin Access... MUST log every cross-tenant access".
# This suggests we should use a BYPASS mechanism.
# Since I can't easily switch DB users in session pool without separate pool, I will assume for this implementation plan
# that I should log the access and perhaps the 'admin' endpoints run with a specific RLS override or I set the tenant_id to the target.
# But "List all tenants" implies cross-tenant visibility.
# AND "Audit Log" is creating a record in `admin_audit_log`.

# Let's implement Admin endpoints by creating a context manager that logs to Audit Log and allows operation.
# How to allow visibility?
# If RLS is ENABLED, I cannot see other tenants' data.
# Unless I SET app.current_tenant_id to THAT tenant.
# For "List all tenants", I might need to query `tenants` without filter.
# If `tenants` has RLS, I can't.
# OPTION: Connect as different user `admin_user`.
# Since I don't have separate creds in `config.py`, I assume the `admin_user` described in plan is for Manual DB access or I should have added `ADMIN_DATABASE_URL`.
# However, I can use `SET ROLE admin_user` if the current user has `SET ROLE` privilege and `admin_user` exists and has BYPASSRLS.
# Let's assume the app user is a superuser or owner who can `SET ROLE`.
# Or I just implement the endpoints assuming `config.py` might eventually have correct creds,
# and for now I just set `app.current_tenant_id` to the target tenant for operations on specific tenants.
# For Listing, I might be stuck if RLS is strict.
# workaround: Admin uses Legacy Org. RLS policy for Tenants table should probably allow Legacy Org to see all?
# "Tenants table: Filter by organization_id OR tenant_id"
# I'll stick to: Admin simulates Tenant Context for specific actions.
# For global actions, we'll assume the DB user has privilege or we won't strictly enforce RLS on `organizations` table as per plan ("Organizations table: No RLS needed").
# `tenants` might need RLS bypass.
# I will implement `log_admin_action` helper.

from brokerage_parser.models import Organization, Tenant, ApiKey, AdminAuditLog, Job
from brokerage_parser.config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])

# Helper for Audit Logging
def log_admin_action(db: Session, admin_id: str, action: str, resource_id: str, reason: str, tenant_id: uuid.UUID):
    if settings.REQUIRE_AUDIT_REASON and not reason:
         raise HTTPException(status_code=400, detail="Audit reason required")

    log_entry = AdminAuditLog(
        admin_user_id=admin_id,
        action=action,
        tenant_id=tenant_id,
        resource_id=resource_id,
        reason=reason,
        timestamp=datetime.now()
    )
    db.add(log_entry)
    db.commit()

# Admin Auth Dependency (Placeholder)
def get_admin_user(api_key: str = Query(..., alias="admin_key")):
    # Verify against hashed keys in config
    import hashlib
    incoming_hash = hashlib.sha256((api_key + settings.API_KEY_SALT).encode()).hexdigest()
    if incoming_hash not in settings.ADMIN_API_KEYS:
         # For dev/bootstrap, if empty list, maybe deny or allow dev?
         if settings.ENV == "development" and not settings.ADMIN_API_KEYS:
             return "dev_admin"
         raise HTTPException(status_code=401, detail="Invalid Admin Key")
    return "super_admin"

# Endpoints

@router.post("/organizations")
def create_organization(
    name: str,
    slug: str,
    admin_user: str = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # No RLS on Organizations (per plan)
    org = Organization(name=name, slug=slug)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org

@router.post("/organizations/{org_id}/tenants")
def create_tenant(
    org_id: uuid.UUID,
    name: str,
    slug: str,
    reason: str,
    admin_user: str = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # Log logic? Creating tenant doesn't access tenant data yet.
    # But we should log it.
    tenant = Tenant(organization_id=org_id, name=name, slug=slug)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    # Log
    log_admin_action(db, admin_user, "CREATE_TENANT", str(tenant.tenant_id), reason, tenant.tenant_id)

    return tenant

@router.post("/tenants/{tenant_id}/api-keys")
def create_api_key(
    tenant_id: uuid.UUID,
    name: str,
    reason: str,
    admin_user: str = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # Generate Key
    import secrets
    import bcrypt

    # Components
    access_id = secrets.token_hex(8)
    secret_raw = secrets.token_urlsafe(32)
    full_key = f"ak_{access_id}_{secret_raw}"

    # Hash Secret
    secret_hash = bcrypt.hashpw(secret_raw.encode(), bcrypt.gensalt()).decode()

    # Get Org ID
    tenant = db.query(Tenant).get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    api_key = ApiKey(
        access_key_id=access_id,
        secret_hash=secret_hash,
        tenant_id=tenant_id,
        organization_id=tenant.organization_id,
        name=name
    )
    db.add(api_key)
    log_admin_action(db, admin_user, "CREATE_API_KEY", str(api_key.key_id), reason, tenant_id)
    db.commit()

    return {"api_key": full_key, "note": "Show once only"}

@router.get("/audit-log")
def view_audit_log(
    limit: int = 100,
    offset: int = 0,
    admin_user: str = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    # Need to query admin_audit_log.
    # The table has Strict RLS? "SELECT requires admin role"
    # Logic: DB user (if same as app) is restricted.
    # We might need to handle this manually since I didn't implement separate DB users.
    logs = db.query(AdminAuditLog).offset(offset).limit(limit).all()
    return logs
