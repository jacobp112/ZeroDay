import time
import logging
from typing import Tuple, Optional
import redis
from brokerage_parser.config import settings

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    def _get_key(self, tenant_id: str, limit_type: str) -> str:
        return f"ratelimit:{tenant_id}:{limit_type}"

    def check_rate_limit(
        self,
        tenant_id: str,
        limit_type: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int, float]:
        """
        Checks if a request is allowed under the sliding window rate limit.
        Returns: (allowed: bool, remaining: int, reset_time: float)
        """
        if not settings.RATE_LIMIT_ENABLED:
            return True, max_requests, 0.0

        key = self._get_key(tenant_id, limit_type)
        now = time.time()
        window_start = now - window_seconds

        try:
            pipeline = self.redis.pipeline()
            # 1. Remove entries older than window
            pipeline.zremrangebyscore(key, 0, window_start)
            # 2. Count requests in current window
            pipeline.zcard(key)
            # 3. Get oldest remaining request to calculate reset time
            pipeline.zrange(key, 0, 0, withscores=True)
            # 4. Set expire on key to auto-cleanup inactive tenants
            pipeline.expire(key, window_seconds + 60)

            results = pipeline.execute()

            # results[0] is count of removed items
            current_count = results[1]
            oldest_request = results[2] # List of (member, score)

            remaining = max(0, max_requests - current_count)
            allowed = remaining > 0

            # Calculate reset time (when the oldest request expires)
            if oldest_request:
                reset_timestamp = oldest_request[0][1] + window_seconds
            else:
                reset_timestamp = now + window_seconds if not allowed else now

            # Record Metric
            try:
                from brokerage_parser.monitoring.metrics import RATE_LIMIT_HITS
                result_label = "allowed" if allowed else "denied"
                RATE_LIMIT_HITS.labels(
                    tenant_id=tenant_id,
                    limit_type=limit_type,
                    result=result_label
                ).inc()
            except ImportError:
                pass # Avoid circular imports if any, or test issues

            return allowed, remaining, reset_timestamp

        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            # Fail open for availability
            return True, 1, 0.0

    def record_request(self, tenant_id: str, limit_type: str) -> None:
        """
        Records a request in the sliding window.
        """
        if not settings.RATE_LIMIT_ENABLED:
            return

        key = self._get_key(tenant_id, limit_type)
        now = time.time()

        try:
            # Add current timestamp as both member and score
            # We add a tiny random suffix or just use unique members if needed?
            # ZADD logic: score=timestamp, member=timestamp.
            # Collision risk: If multiple requests happen at EXACT same float timestamp.
            # Fix: Append unique ID to member.
            member = f"{now}:{time.time_ns()}"
            self.redis.zadd(key, {member: now})
        except redis.RedisError as e:
            logger.error(f"Redis error recording request: {e}")

    def get_current_usage(self, tenant_id: str, limit_type: str, window_seconds: int) -> int:
        """
        Get current usage count for a tenant.
        """
        key = self._get_key(tenant_id, limit_type)
        now = time.time()
        window_start = now - window_seconds

        try:
            # Cleanup first to get accurate count
            self.redis.zremrangebyscore(key, 0, window_start)
            return self.redis.zcard(key)
        except redis.RedisError:
            return 0

    def reset_limits(self, tenant_id: str, limit_type: str) -> None:
        """
        Emergency reset of rate limits for a tenant.
        """
        key = self._get_key(tenant_id, limit_type)
        try:
            self.redis.delete(key)
        except redis.RedisError as e:
            logger.error(f"Failed to reset limits: {e}")
