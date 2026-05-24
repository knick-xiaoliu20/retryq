import pytest
from unittest.mock import MagicMock, patch
from retryq.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from retryq.circuit_worker import CircuitWorker


@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.dequeue.return_value = None
    return q


@pytest.fixture
def handler():
    return MagicMock()


@pytest.fixture
def breaker():
    config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
    return CircuitBreaker(config)


@pytest.fixture
def worker(mock_queue, handler, breaker):
    return CircuitWorker(mock_queue, handler, breaker=breaker)


def test_process_one_no_task_returns_false(worker, mock_queue):
    mock_queue.dequeue.return_value = None
    assert worker.process_one() is False


def test_process_one_success_acknowledges_task(worker, mock_queue, handler):
    task = {"id": "t1", "payload": "data"}
    mock_queue.dequeue.return_value = task
    result = worker.process_one()
    assert result is True
    handler.assert_called_once_with(task)
    mock_queue.acknowledge.assert_called_once_with("t1")


def test_process_one_success_records_to_breaker(worker, mock_queue, breaker):
    task = {"id": "t2", "payload": "x"}
    mock_queue.dequeue.return_value = task
    worker.process_one()
    assert breaker._failure_count == 0
    assert breaker.state == CircuitState.CLOSED


def test_process_one_failure_records_to_breaker(worker, mock_queue, handler, breaker):
    task = {"id": "t3", "payload": "x"}
    mock_queue.dequeue.return_value = task
    handler.side_effect = RuntimeError("boom")
    result = worker.process_one()
    assert result is False
    assert breaker._failure_count == 1
    mock_queue.requeue.assert_called_once_with(task)


def test_open_circuit_blocks_processing(worker, mock_queue, handler, breaker):
    task = {"id": "t4", "payload": "x"}
    mock_queue.dequeue.return_value = task
    handler.side_effect = RuntimeError("fail")
    worker.process_one()
    worker.process_one()
    assert breaker.state == CircuitState.OPEN
    result = worker.process_one()
    assert result is False
    assert mock_queue.dequeue.call_count == 2


def test_circuit_state_property(worker, breaker):
    assert worker.circuit_state == CircuitState.CLOSED
    for _ in range(2):
        breaker.record_failure()
    assert worker.circuit_state == CircuitState.OPEN
