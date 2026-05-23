import time
import pytest
from unittest.mock import MagicMock, patch
from retryq.rate_limiter import RateLimiter


@pytest.fixture
def redis_mock():
    return MagicMock()


@pytest.fixture
def limiter(redis_mock):
    return RateLimiter(
        redis_client=redis_mock,
        key="retryq:rate:test",
        max_tokens=5,
        refill_rate=1.0,
        ttl=60,
    )


def test_acquire_succeeds_when_bucket_is_full(limiter, redis_mock):
    """First acquire on an empty key should always succeed."""
    redis_mock.pipeline.return_value.execute.return_value = [{}]
    result = limiter.acquire(tokens=1)
    assert result is True


def test_acquire_fails_when_no_tokens_left(limiter, redis_mock):
    """Acquire should fail when stored tokens are 0 and no time has elapsed."""
    now = time.monotonic()
    state = {b"tokens": b"0.0", b"last_refill": str(now).encode()}
    redis_mock.pipeline.return_value.execute.return_value = [state]

    with patch.object(limiter, "_now", return_value=now):
        result = limiter.acquire(tokens=1)

    assert result is False


def test_acquire_succeeds_after_refill(limiter, redis_mock):
    """Tokens should be refilled based on elapsed time."""
    past = time.monotonic() - 3.0  # 3 seconds ago → +3 tokens refilled
    state = {b"tokens": b"0.0", b"last_refill": str(past).encode()}
    redis_mock.pipeline.return_value.execute.return_value = [state]

    result = limiter.acquire(tokens=1)
    assert result is True


def test_acquire_does_not_exceed_max_tokens(limiter, redis_mock):
    """Refill should be capped at max_tokens."""
    past = time.monotonic() - 100.0  # huge elapsed time
    state = {b"tokens": b"0.0", b"last_refill": str(past).encode()}
    redis_mock.pipeline.return_value.execute.return_value = [state]

    # Capture the hset call to inspect stored tokens
    stored = {}

    def capture_hset(key, mapping):
        stored.update(mapping)

    pipe_mock = MagicMock()
    pipe_mock.execute.return_value = [None, None]
    pipe_mock.hset.side_effect = capture_hset
    redis_mock.pipeline.return_value = pipe_mock
    # First pipeline call (read) returns the state
    pipe_mock.execute.side_effect = [[state], [None, None]]

    limiter.acquire(tokens=1)
    assert stored.get("tokens", limiter.max_tokens + 1) <= limiter.max_tokens


def test_available_tokens_returns_max_when_no_state(limiter, redis_mock):
    redis_mock.hgetall.return_value = {}
    tokens = limiter.available_tokens()
    assert tokens == limiter.max_tokens


def test_available_tokens_reflects_stored_value(limiter, redis_mock):
    now = time.monotonic()
    redis_mock.hgetall.return_value = {
        b"tokens": b"3.0",
        b"last_refill": str(now).encode(),
    }
    with patch.object(limiter, "_now", return_value=now):
        tokens = limiter.available_tokens()
    assert pytest.approx(tokens, abs=0.1) == 3.0


def test_reset_deletes_key(limiter, redis_mock):
    limiter.reset()
    redis_mock.delete.assert_called_once_with("retryq:rate:test")
