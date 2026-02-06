import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.routing import Match
from prometheus_client import Counter, Histogram, Gauge

# Metrics
REQUESTS = Counter(
    "parsefin_http_requests_total",
    "Total count of requests by method, status and path.",
    ["method", "path", "status", "tenant_id"]
)

RESPONSES = Histogram(
    "parsefin_http_request_duration_seconds",
    "HTTP request latency (seconds).",
    ["method", "path", "tenant_id"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0)
)

JOB_PROCESSING_SECONDS = Histogram(
    "parsefin_job_processing_seconds",
    "Time spent processing a brokerage statement job",
    ["tenant_id", "broker"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600)
)

ACTIVE_JOBS = Gauge(
    "parsefin_active_jobs",
    "Number of jobs currently processing",
    ["tenant_id"]
)

RATE_LIMIT_HITS = Counter(
    "parsefin_rate_limit_hits_total",
    "Total number of rate limit checks by result (allowed/denied)",
    ["tenant_id", "limit_type", "result"]
)

USAGE_EVENTS = Counter(
    "parsefin_usage_events_total",
    "Total usage events recorded",
    ["tenant_id", "event_type"]
)

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()
        method = request.method

        # Determine path template (e.g. /users/{id}) to avoid high cardinality
        # This is tricky with BaseHTTPMiddleware
        path_template = "unknown"
        for route in request.app.routes:
            match, child_scope = route.matches(request.scope)
            if match == Match.FULL:
                path_template = route.path
                break

        # Fallback if not matched (e.g. 404)
        if path_template == "unknown":
            path_template = request.url.path

        # Determine Tenant ID from State (set by TenantContextMiddleware)
        # If not set (health check, public), use "system"
        tenant_id = getattr(request.state, "tenant_id", "system")
        if not tenant_id:
             tenant_id = "system"

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            process_time = time.time() - start_time

            # Record Metrics
            REQUESTS.labels(
                method=method,
                path=path_template,
                status=status_code,
                tenant_id=str(tenant_id)
            ).inc()

            RESPONSES.labels(
                method=method,
                path=path_template,
                tenant_id=str(tenant_id)
            ).observe(process_time)

        return response
