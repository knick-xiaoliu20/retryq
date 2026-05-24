import time
import pytest
from retryq.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState


@pytest.fixture
def breaker():
    config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1.0)
    return CircuitBreaker(config)


def test_initial_state_is_closed(breaker):
    assert breaker.state == CircuitState.CLOSED


def test_allow_request_when_closed(breaker):
    assert breaker.allow_request() is True


def test_opens_after_threshold_failures(breaker):
    for _ in range(3):
        breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_blocks_request_when_open(breaker):
    for _ in range(3):
        breaker.record_failure()
    assert breaker.allow_request() is False


def test_success_resets_failure_count(breaker):
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    assert breaker._failure_count == 0
    assert breaker.state == CircuitState.CLOSED


def test_transitions_to_half_open_after_timeout(breaker):
    for _ in range(3):
        breaker.record_failure()
    # Manually backdate the failure time
    breaker._last_failure_time = time.monotonic() - 2.0
    assert breaker.state == CircuitState.HALF_OPEN


def test_half_open_allows_limited_calls(breaker):
    for _ in range(3):
        breaker.record_failure()
    breaker._last_failure_time = time.monotonic() - 2.0
    assert breaker.state == CircuitState.HALF_OPEN
    assert breaker.allow_request() is True
    breaker._half_open_calls = 1
    assert breaker.allow_request() is False


def test_success_in_half_open_closes_circuit(breaker):
    for _ in range(3):
        breaker.record_failure()
    breaker._state = CircuitState.HALF_OPEN
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED


def test_failure_in_half_open_reopens_circuit(breaker):
    for _ in range(3):
        breaker.record_failure()
    breaker._state = CircuitState.HALF_OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_reset_clears_state(breaker):
    for _ in range(3):
        breaker.record_failure()
    breaker.reset()
    assert breaker.state == CircuitState.CLOSED
    assert breaker._failure_count == 0


def test_invalid_config_raises():
    with pytest.raises(ValueError):
        CircuitBreakerConfig(failure_threshold=0)
    with pytest.raises(ValueError):
        CircuitBreakerConfig(recovery_timeout=-1)
    with pytest.raises(ValueError):
        CircuitBreakerConfig(half_open_max_calls=0)
