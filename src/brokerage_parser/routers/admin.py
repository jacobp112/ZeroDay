import uuid
import secrets
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel, EmailStr, Field

from brokerage_parser.db import get_db
from brokerage_parser.models.tenant import Organization, Tenant, ApiKey, AdminAuditLog
from brokerage_parser.auth.admin import get_current_admin, AdminUser
from brokerage_parser.core.audit import create_audit_log
from brokerage_parser.core.security import get_password_hash
from brokerage_parser.config import settings

router = APIRouter(prefix="/admin", tags=["Admin API"])

# --- Models ---

class OrganizationBase(BaseModel):
    name: str
    slug: str
    billing_email: Optional[EmailStr] = None

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TenantBase(BaseModel):
    name: str
    slug: str

class TenantCreate(TenantBase):
    organization_id: uuid.UUID

class TenantResponse(TenantBase):
    tenant_id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ApiKeyCreate(BaseModel):
    name: str
    reason: str = Field(..., description="Reason for creation (Auditing)")

class ApiKeyResponse(BaseModel):
    key_id: uuid.UUID
    access_key_id: str
    name: Optional[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]

    class Config:
        from_attributes = True

class ApiKeySecretResponse(ApiKeyResponse):
    secret_key: str

class AuditLogResponse(BaseModel):
    id: int
    admin_user_id: str
    action: str
    tenant_id: Optional[uuid.UUID]
    resource_id: Optional[str]
    reason: str
    ip_address: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True

# --- Endpoints ---

# 1. Organizations

@router.get("/organizations", response_model=List[OrganizationResponse])
async def list_organizations(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    query = db.query(Organization)
    if search:
        query = query.filter(Organization.name.ilike(f"%{search}%"))
    return query.offset(skip).limit(limit).all()

@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    org_in: OrganizationCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    # Check slug uniqueness
    existing = db.query(Organization).filter(Organization.slug == org_in.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Organization slug already exists")

    org = Organization(**org_in.dict())
    db.add(org)
    db.commit()
    db.refresh(org)

    create_audit_log(
        db, admin.email, "ORG_CREATE", request.client.host,
        resource_id=str(org.organization_id), reason="Created organization via Admin API"
    )
    return org

@router.delete("/organizations/{org_id}", status_code=204)
async def delete_organization(
    org_id: uuid.UUID,
    request: Request,
    reason: str = Query(..., min_length=5),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    org = db.query(Organization).get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Soft delete? Or hard delete?
    org.is_active = False
    db.commit()

    create_audit_log(
        db, admin.email, "ORG_DELETE", request.client.host,
        resource_id=str(org.organization_id), reason=reason
    )
    return None

# 2. Tenants

@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    org_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    query = db.query(Tenant)
    if org_id:
        query = query.filter(Tenant.organization_id == org_id)
    return query.offset(skip).limit(limit).all()

@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    tenant_in: TenantCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    # Verify Org exists
    org = db.query(Organization).get(tenant_in.organization_id)
    if not org:
         raise HTTPException(status_code=400, detail="Organization not found")

    # Check slug uniqueness within org? Or globally?
    # Model says unique constraint on (org_id, slug).
    existing = db.query(Tenant).filter(
        Tenant.organization_id == tenant_in.organization_id,
        Tenant.slug == tenant_in.slug
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant slug already exists in this organization")

    tenant = Tenant(**tenant_in.dict())
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    create_audit_log(
        db, admin.email, "TENANT_CREATE", request.client.host,
        resource_id=str(tenant.tenant_id), tenant_id=str(tenant.tenant_id),
        reason="Created tenant via Admin API"
    )
    return tenant

# 3. API Keys

@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    query = db.query(ApiKey)
    if search:
        query = query.filter(ApiKey.access_key_id.ilike(f"%{search}%"))
    return query.offset(skip).limit(limit).all()

@router.post("/tenants/{tenant_id}/api-keys", response_model=ApiKeySecretResponse, status_code=201)
async def create_api_key(
    tenant_id: uuid.UUID,
    key_in: ApiKeyCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    tenant = db.query(Tenant).get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Generate Keys
    # access_key_id: prefix "pk_" + random
    access_key_id = f"pk_{secrets.token_hex(8)}"
    secret_key = secrets.token_urlsafe(32)
    secret_hash = get_password_hash(secret_key)

    api_key = ApiKey(
        access_key_id=access_key_id,
        secret_hash=secret_hash,
        tenant_id=tenant_id,
        organization_id=tenant.organization_id,
        name=key_in.name,
        is_active=True
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    create_audit_log(
        db, admin.email, "KEY_CREATE", request.client.host,
        resource_id=str(api_key.key_id), tenant_id=str(tenant.tenant_id),
        reason=key_in.reason
    )

    # Return secret ONCE
    # Return secret ONCE
    return {
        "key_id": api_key.key_id,
        "access_key_id": api_key.access_key_id,
        "name": api_key.name,
        "is_active": api_key.is_active,
        "created_at": api_key.created_at,
        "last_used_at": api_key.last_used_at,
        "secret_key": secret_key
    }

@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    request: Request,
    reason: str = Query(..., min_length=5),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    key = db.query(ApiKey).get(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API Key not found")

    key.is_active = False
    db.commit()

    create_audit_log(
        db, admin.email, "KEY_REVOKE", request.client.host,
        resource_id=str(key.key_id), tenant_id=str(key.tenant_id),
        reason=reason
    )
    return None

# 4. Audit Log

@router.get("/audit-log", response_model=List[AuditLogResponse])
async def list_audit_logs(
    admin_user: Optional[str] = None,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    query = db.query(AdminAuditLog).order_by(desc(AdminAuditLog.timestamp))
    if admin_user:
        query = query.filter(AdminAuditLog.admin_user_id == admin_user)
    if action:
        query = query.filter(AdminAuditLog.action == action)

    return query.offset(skip).limit(limit).all()

# 5. Health

@router.get("/health/details", tags=["System"])
async def check_health_details(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    # Detailed health check for admin
    # DB
    db_status = "unknown"
    try:
        db.execute(func.now())
        db_status = "up"
    except Exception as e:
        db_status = f"down: {str(e)}"

    return {
        "status": "ok" if db_status == "up" else "degraded",
        "components": {
            "database": db_status,
            # Add Redis/Workers/Storage checks here
        },
        "timestamp": datetime.now(timezone.utc)
    }
