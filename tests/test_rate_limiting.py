import pytest
import time
from unittest.mock import MagicMock, patch
from brokerage_parser.core.rate_limiter import RateLimiter
from brokerage_parser.config import settings
import redis

# We can mock redis for unit tests to ensure logic is correct without dependency
# For integration tests, we'd use the real redis.
# Let's do a mix or stick to mocking for stability in CI, but here we can try mocking first.

@pytest.fixture
def mock_redis():
    with patch('brokerage_parser.core.rate_limiter.redis.from_url') as mock_from_url:
        mock_client = MagicMock()
        mock_from_url.return_value = mock_client
        pipeline = MagicMock()
        mock_client.pipeline.return_value = pipeline
        yield mock_client, pipeline

@pytest.fixture
def rate_limiter(mock_redis):
    return RateLimiter()

def test_check_rate_limit_allowed(rate_limiter, mock_redis):
    client, pipeline = mock_redis

    # Setup mock pipeline return values
    # results[1] is count (zcard)
    # results[2] is oldest (zrange)
    pipeline.execute.return_value = [0, 5, [("timestamp", 1234567890.0)]]

    allowed, remaining, reset = rate_limiter.check_rate_limit("tenant1", "jobs", 10, 3600)

    assert allowed is True
    assert remaining == 5 # 10 - 5
    assert pipeline.zremrangebyscore.called
    assert pipeline.zcard.called

def test_check_rate_limit_exceeded(rate_limiter, mock_redis):
    client, pipeline = mock_redis

    # Count is 10, max is 10. Next request should fail?
    # Logic: allowed = remaining > 0. remaining = max(0, 10 - 10) = 0.
    # So valid checks: if current count is 10, and max is 10, existing usage is 10.
    # Current request NOT added yet. "check" usually implies "can I do this?".
    # If using token bucket, we check then consume.
    # My implementation:
    # current_count = redis.zcard (existing requests)
    # remaining = max - current_count
    # allowed = remaining > 0
    # If remaining is 0, allowed is False.
    # So if there are 10 items, and limit is 10, remaining is 0, allowed is False.
    # This means capturing usage APRIORI.

    pipeline.execute.return_value = [0, 10, [("timestamp", 1234567890.0)]]

    allowed, remaining, reset = rate_limiter.check_rate_limit("tenant1", "jobs", 10, 3600)

    assert allowed is False
    assert remaining == 0

def test_record_request(rate_limiter, mock_redis):
    client, _ = mock_redis
    rate_limiter.record_request("tenant1", "jobs")
    assert client.zadd.called

def test_fail_open_on_redis_error(rate_limiter, mock_redis):
    client, pipeline = mock_redis
    pipeline.execute.side_effect = redis.RedisError("Redis connection failed")

    allowed, remaining, reset = rate_limiter.check_rate_limit("tenant1", "jobs", 10, 3600)

    # Should fail open
    assert allowed is True
    assert remaining == 1
