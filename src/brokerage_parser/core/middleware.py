from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import HTTPException
import hashlib
from typing import Optional

from brokerage_parser.db import SessionLocal
from brokerage_parser.models import ApiKey
from brokerage_parser.config import settings

class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health check and open endpoints
        path = request.url.path
        if any(path.startswith(p) for p in ["/health", "/metrics", "/docs", "/openapi.json"]):
            return await call_next(request)

        # Skip for Admin and Portal APIs (they handle their own auth)
        if request.url.path.startswith("/admin") or request.url.path.startswith("/portal"):
            return await call_next(request)

        # 1. Extract API Key
        api_key = request.headers.get("X-API-Key")

        tenant_id = None
        org_id = None

        if api_key:
             # 2. Lookup Key
             # We need a DB session. Middleware context is tricky for DB sessions?
             # Ideally we check cache (Redis).
             # For this implementation, we can use a fresh session.

             # If development and no key, use legacy tenant?
             if settings.ENV == "development" and not api_key:
                  # Maybe allow bypass or auto-inject legacy?
                  # Plan says "Extracts X-API-Key... Returns 401 if key not found".
                  # So we enforce it unless specifically testing.
                  pass

             # Hash key
             import bcrypt

             # Format: ak_{access_key_id}_{secret}
             if not api_key.startswith("ak_"):
                 if settings.ENABLE_TENANT_ISOLATION:
                      raise HTTPException(status_code=401, detail="Invalid API Key format")
                 return await call_next(request)

             try:
                 _, access_id, secret = api_key.split("_", 2)
             except ValueError:
                 if settings.ENABLE_TENANT_ISOLATION:
                      raise HTTPException(status_code=401, detail="Invalid API Key format")
                 return await call_next(request)

             session = SessionLocal()
             try:
                 key_record = session.query(ApiKey).filter(ApiKey.access_key_id == access_id, ApiKey.is_active == True).first()
                 if key_record:
                     # Verify Secret
                     if bcrypt.checkpw(secret.encode(), key_record.secret_hash.encode()):
                         tenant_id = str(key_record.tenant_id)
                         org_id = str(key_record.organization_id)
                     else:
                         if settings.ENABLE_TENANT_ISOLATION:
                             raise HTTPException(status_code=401, detail="Invalid API Key")
             finally:
                 session.close()

        # 3. Fallback for Development / Tests (Optional)
        if not tenant_id and not settings.ENABLE_TENANT_ISOLATION:
             tenant_id = settings.LEGACY_TENANT_ID
             org_id = settings.LEGACY_ORG_ID

        # 4. Set State
        if tenant_id and org_id:
            request.state.tenant_id = tenant_id
            request.state.org_id = org_id
        else:
            # If Enforce Isolation is True, we reject?
            # Or we let Endpoint dependency fail?
            # Middleware just populates state. `get_db` or `get_current_tenant` dependency enforces.
            # But the plan says "Returns 401 ... if key not found".
            if settings.ENABLE_TENANT_ISOLATION:
                raise HTTPException(status_code=401, detail="Authentication required")

        response = await call_next(request)
        return response
