from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import HTTPException
import hashlib
from typing import Optional
import time

from brokerage_parser.db import SessionLocal
from brokerage_parser.models import ApiKey, TenantRateLimit
from brokerage_parser.config import settings
from brokerage_parser.core.rate_limiter import RateLimiter

# Initialize RateLimiter globally or per request? Globally is better for connection pooling.
# But initialization might need settings which might be loaded.
# Lazy loading or global var?
_rate_limiter = None

def get_rate_limiter():
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

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
                      # Return JSON response directly for middleware errors
                      return JSONResponse(status_code=401, content={"detail": "Invalid API Key format"})
                 return await call_next(request)

             try:
                 _, access_id, secret = api_key.split("_", 2)
             except ValueError:
                 if settings.ENABLE_TENANT_ISOLATION:
                      return JSONResponse(status_code=401, content={"detail": "Invalid API Key format"})
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
                             return JSONResponse(status_code=401, content={"detail": "Invalid API Key"})
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
            if settings.ENABLE_TENANT_ISOLATION:
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})

        response = await call_next(request)
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip for health/metrics/docs (same as Auth)
        path = request.url.path
        if any(path.startswith(p) for p in ["/health", "/metrics", "/docs", "/openapi.json"]):
             return await call_next(request)

        # Admin/Portal logic? Plan says "Add rate limit middleware".
        # Assuming Admin is exempt or has different limits?
        # Let's skip Admin/Portal for now as they are internal-facing or have auth based sessions.
        if request.url.path.startswith("/admin") or request.url.path.startswith("/portal"):
             return await call_next(request)

        # Get Tenant ID from state (set by TenantContextMiddleware)
        if not hasattr(request.state, "tenant_id"):
             # Should have been handled by auth, but if we proceeded...
             return await call_next(request)

        tenant_id = request.state.tenant_id

        # Determine Limit Type
        # Parse endpoints = jobs_per_hour
        # Everything else = api_calls_per_hour
        limit_type = "api_calls"
        default_limit = settings.RATE_LIMIT_DEFAULT_API_CALLS_PER_HOUR

        if request.url.path.startswith("/v1/parse"):
            limit_type = "jobs"
            default_limit = settings.RATE_LIMIT_DEFAULT_JOBS_PER_HOUR

        # Get Limits for Tenant (Cache this in Redis later!)
        # For now, quick DB lookup or just use defaults to start?
        # Plan says "Extracts tenant... Checks applicable rate limit".
        # ideally we don't hit DB on every request.
        # Strategy: Use defaults from settings for now, or fetch from Redis cache if available.
        # Step 3 says "fetch limits from database".
        # RateLimiter uses arguments `max_requests`. So we need to pass it.
        # Optimization: Fetch limits and cache in Redis `ratelimit:config:{tenant_id}`

        limit = default_limit
        # TODO: Lookup tenant-specific limits from DB/Redis

        # Check Rate Limit
        limiter = get_rate_limiter()
        allowed, remaining, reset_time = limiter.check_rate_limit(
            tenant_id,
            limit_type,
            limit,
            3600 # 1 hour window
        )

        if not allowed:
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(reset_time)),
                "Retry-After": str(int(reset_time - time.time()))
            }
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers=headers
            )

        # Determine concurrent jobs limit if it's a job submission?
        # That's tricky in middleware before body parsing.
        # Let's stick to request limits here. Concurrent is handled at Worker/Logic level or maybe here?
        # Plan says "Separate buckets for concurrent_jobs".
        # Concurrent limit usually means "in progress".
        # Redis INCR when start, DECR when finish.
        # Middleware can INCR, but when to DECR? Response finish? Or Worker finish?
        # For long running jobs, worker finish.
        # This middleware only handles Request Rate Limits (Throttling). concurrency is separate.

        # Record request
        limiter.record_request(tenant_id, limit_type)

        response = await call_next(request)

        # Add headers to successful response
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))

        return response
