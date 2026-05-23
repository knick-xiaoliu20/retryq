import json
import time
import pytest
from unittest.mock import MagicMock, patch

from retryq.queue import RetryQueue


@pytest.fixture
def redis_mock():
    return MagicMock()


@pytest.fixture
def queue(redis_mock):
    return RetryQueue(
        redis_client=redis_mock,
        queue_name="test",
        max_retries=3,
        base_delay=1.0,
        backoff_factor=2.0,
    )


def test_enqueue_pushes_to_pending(queue, redis_mock):
    queue.enqueue("task-1", {"key": "value"})
    redis_mock.rpush.assert_called_once()
    args = redis_mock.rpush.call_args[0]
    assert args[0] == "test:pending"
    data = json.loads(args[1])
    assert data["task_id"] == "task-1"
    assert data["attempt"] == 0


def test_dequeue_returns_none_when_empty(queue, redis_mock):
    redis_mock.lpop.return_value = None
    assert queue.dequeue() is None


def test_dequeue_returns_task(queue, redis_mock):
    task = {"task_id": "t1", "payload": {"x": 1}, "attempt": 0}
    redis_mock.lpop.return_value = json.dumps(task)
    result = queue.dequeue()
    assert result["task_id"] == "t1"


def test_retry_schedules_task(queue, redis_mock):
    task = {"task_id": "t2", "payload": {}, "attempt": 0}
    result = queue.retry(task)
    assert result is True
    redis_mock.zadd.assert_called_once()
    key, mapping = redis_mock.zadd.call_args[0]
    assert key == "test:scheduled"
    stored_task = json.loads(list(mapping.keys())[0])
    assert stored_task["attempt"] == 1


def test_retry_moves_to_dead_after_max_retries(queue, redis_mock):
    task = {"task_id": "t3", "payload": {}, "attempt": 3}
    result = queue.retry(task)
    assert result is False
    redis_mock.rpush.assert_called_once()
    assert redis_mock.rpush.call_args[0][0] == "test:dead"


def test_poll_scheduled_moves_due_tasks(queue, redis_mock):
    raw = json.dumps({"task_id": "t4", "payload": {}, "attempt": 1})
    redis_mock.zrangebyscore.return_value = [raw]
    pipe_mock = MagicMock()
    redis_mock.pipeline.return_value = pipe_mock

    count = queue.poll_scheduled()
    assert count == 1
    pipe_mock.execute.assert_called_once()


def test_poll_scheduled_returns_zero_when_empty(queue, redis_mock):
    redis_mock.zrangebyscore.return_value = []
    assert queue.poll_scheduled() == 0
