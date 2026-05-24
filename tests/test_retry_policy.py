import pytest
from retryq.retry_policy import RetryPolicy


def test_defaults():
    policy = RetryPolicy()
    assert policy.max_attempts == 5
    assert policy.base_delay == 1.0
    assert policy.max_delay == 60.0
    assert policy.backoff_factor == 2.0
    assert policy.jitter is False


def test_invalid_max_attempts_raises():
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)


def test_invalid_base_delay_raises():
    with pytest.raises(ValueError, match="base_delay"):
        RetryPolicy(base_delay=0)


def test_max_delay_less_than_base_raises():
    with pytest.raises(ValueError, match="max_delay"):
        RetryPolicy(base_delay=10.0, max_delay=5.0)


def test_invalid_backoff_factor_raises():
    with pytest.raises(ValueError, match="backoff_factor"):
        RetryPolicy(backoff_factor=0.5)


def test_compute_delay_exponential():
    policy = RetryPolicy(base_delay=1.0, backoff_factor=2.0, max_delay=100.0)
    assert policy.compute_delay(1) == 1.0
    assert policy.compute_delay(2) == 2.0
    assert policy.compute_delay(3) == 4.0
    assert policy.compute_delay(4) == 8.0


def test_compute_delay_capped_at_max():
    policy = RetryPolicy(base_delay=1.0, backoff_factor=2.0, max_delay=5.0)
    assert policy.compute_delay(10) == 5.0


def test_compute_delay_with_jitter_within_range():
    policy = RetryPolicy(base_delay=1.0, backoff_factor=2.0, max_delay=100.0, jitter=True)
    for _ in range(20):
        delay = policy.compute_delay(3)  # uncapped would be 4.0
        assert 0.0 <= delay <= 4.0


def test_should_retry_within_limit():
    policy = RetryPolicy(max_attempts=3)
    assert policy.should_retry(1) is True
    assert policy.should_retry(2) is True


def test_should_retry_at_limit_returns_false():
    policy = RetryPolicy(max_attempts=3)
    assert policy.should_retry(3) is False


def test_should_retry_with_retryable_exception():
    policy = RetryPolicy(max_attempts=5, retryable_exceptions=(ValueError,))
    assert policy.should_retry(1, exc=ValueError("oops")) is True
    assert policy.should_retry(1, exc=TypeError("bad type")) is False


def test_should_retry_no_retryable_filter():
    policy = RetryPolicy(max_attempts=5)
    assert policy.should_retry(1, exc=RuntimeError("any")) is True


def test_to_dict_roundtrip():
    policy = RetryPolicy(max_attempts=3, base_delay=2.0, max_delay=30.0, backoff_factor=3.0)
    d = policy.to_dict()
    restored = RetryPolicy.from_dict(d)
    assert restored.max_attempts == 3
    assert restored.base_delay == 2.0
    assert restored.max_delay == 30.0
    assert restored.backoff_factor == 3.0
