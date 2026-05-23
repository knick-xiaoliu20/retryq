import pytest
from unittest.mock import MagicMock, patch, call

from retryq.worker import Worker
from retryq.queue import RetryQueue


@pytest.fixture
def mock_queue():
    q = MagicMock(spec=RetryQueue)
    q.poll_scheduled.return_value = 0
    return q


@pytest.fixture
def handler():
    return MagicMock()


@pytest.fixture
def worker(mock_queue, handler):
    return Worker(queue=mock_queue, handler=handler, poll_interval=0.0)


def test_process_one_returns_false_when_no_task(worker, mock_queue):
    mock_queue.dequeue.return_value = None
    assert worker.process_one() is False


def test_process_one_calls_handler(worker, mock_queue, handler):
    task = {"task_id": "t1", "payload": {"msg": "hello"}, "attempt": 0}
    mock_queue.dequeue.return_value = task
    result = worker.process_one()
    assert result is True
    handler.assert_called_once_with({"msg": "hello"})


def test_process_one_retries_on_failure(worker, mock_queue, handler):
    task = {"task_id": "t2", "payload": {}, "attempt": 0}
    mock_queue.dequeue.return_value = task
    handler.side_effect = ValueError("boom")
    mock_queue.retry.return_value = True

    result = worker.process_one()
    assert result is True
    mock_queue.retry.assert_called_once_with(task)


def test_process_one_logs_dead_task(worker, mock_queue, handler):
    task = {"task_id": "t3", "payload": {}, "attempt": 5}
    mock_queue.dequeue.return_value = task
    handler.side_effect = RuntimeError("fail")
    mock_queue.retry.return_value = False

    result = worker.process_one()
    assert result is True
    mock_queue.retry.assert_called_once()


def test_run_stops_when_flag_cleared(worker, mock_queue):
    call_count = 0

    def fake_process_one():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            worker.stop()
        return False

    worker.process_one = fake_process_one
    worker.run()
    assert call_count == 2
    assert not worker._running
