from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy import func, text

from brokerage_parser.config import settings
from brokerage_parser.db import get_db
from brokerage_parser.models.tenant import ApiKey, Tenant, Organization
from brokerage_parser.core.security import verify_password

router = APIRouter(prefix="/portal/auth", tags=["Portal Auth"])

security = HTTPBearer()

class PortalLoginRequest(BaseModel):
    access_key_id: str
    secret_key: str

class PortalToken(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class PortalUser(BaseModel):
    tenant_id: str
    organization_id: str
    scope: str = "portal"

def create_portal_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)

    to_encode.update({"exp": expire})
    # Use PORTAL_JWT_SECRET
    secret = settings.PORTAL_JWT_SECRET or settings.ADMIN_JWT_SECRET # Fallback if not set/local
    encoded_jwt = jwt.encode(to_encode, secret, algorithm="HS256")
    return encoded_jwt

def get_current_tenant(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        secret = settings.PORTAL_JWT_SECRET or settings.ADMIN_JWT_SECRET
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        tenant_id: str = payload.get("tenant_id")
        organization_id: str = payload.get("organization_id")
        if tenant_id is None or organization_id is None:
            raise credentials_exception
        return PortalUser(tenant_id=tenant_id, organization_id=organization_id)
    except JWTError:
        raise credentials_exception

@router.post("/login", response_model=PortalToken)
async def portal_login(login_request: PortalLoginRequest, db: Session = Depends(get_db)):
    # 1. Find API Key
    # Set flag to allow RLS bypass for this specific lookup
    db.execute(text("SELECT set_config('app.in_auth_flow', 'true', true)"))
    try:
        api_key = db.query(ApiKey).filter(ApiKey.access_key_id == login_request.access_key_id).first()
    finally:
        # Reset (though transaction scope clears it usually)
        # db.execute(text("RESET app.in_auth_flow")) # Optional if we rely on transaction end
        pass

    # RLS is re-enabled for subsequent queries in this session unless we set it again (scoped to transaction)
    # But for login, we just need this key.
    # NOTE: api_key.tenant relationship access below MIGHT trigger another query?
    # No, usually if eager loaded or if we access it now while session is open.
    # If we access api_key.tenant, it will query Tenant table.
    # Tenant table RLS requires `app.current_tenant_id`.
    # We DO NOT have it set yet!
    # But valid login sets it? No, we set it in Middleware for REQUESTS.
    # Here we are inside the endpoint manually.
    # WE MUST SET THE CONTEXT MANUALLY if we want to access related objects!

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Set context for the rest of this transaction/request so we can access relations like api_key.tenant
    db.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(api_key.tenant_id)})
    db.execute(text("SELECT set_config('app.current_organization_id', :oid, true)"), {"oid": str(api_key.organization_id)})


    # 2. Verify Secret
    if not verify_password(login_request.secret_key, api_key.secret_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 3. Check Active Status
    if not api_key.is_active:
        raise HTTPException(status_code=403, detail="API Key is inactive")

    if not api_key.tenant.is_active:
        raise HTTPException(status_code=403, detail="Tenant is inactive")

    # 4. Generate Token
    access_token_expires = timedelta(hours=24)
    access_token = create_portal_token(
        data={
            "sub": str(api_key.tenant_id),
            "tenant_id": str(api_key.tenant_id),
            "organization_id": str(api_key.organization_id),
            "key_id": str(api_key.key_id)
        },
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": int(access_token_expires.total_seconds())
    }
