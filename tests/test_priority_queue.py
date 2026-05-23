import json
import pytest
from unittest.mock import MagicMock, patch
from retryq.priority_queue import PriorityQueue


@pytest.fixture
def redis_mock():
    return MagicMock()


@pytest.fixture
def pq(redis_mock):
    return PriorityQueue(redis_mock, key_prefix="test:pq")


def test_enqueue_adds_to_sorted_set(pq, redis_mock):
    pq.enqueue("task-1", {"job": "send_email"}, priority=PriorityQueue.PRIORITY_NORMAL)
    assert redis_mock.zadd.called
    key = redis_mock.zadd.call_args[0][0]
    assert key == "test:pq:pending"


def test_enqueue_invalid_priority_raises(pq):
    with pytest.raises(ValueError, match="Invalid priority"):
        pq.enqueue("task-1", {}, priority=99)


def test_enqueue_score_reflects_priority(pq, redis_mock):
    with patch("retryq.priority_queue.time") as mock_time:
        mock_time.time.return_value = 1000.0
        pq.enqueue("t1", {}, priority=PriorityQueue.PRIORITY_CRITICAL)
        score_critical = list(redis_mock.zadd.call_args[0][1].values())[0]

        mock_time.time.return_value = 1001.0
        pq.enqueue("t2", {}, priority=PriorityQueue.PRIORITY_LOW)
        score_low = list(redis_mock.zadd.call_args[0][1].values())[0]

    assert score_critical < score_low


def test_dequeue_returns_none_when_empty(pq, redis_mock):
    redis_mock.zpopmin.return_value = []
    result = pq.dequeue()
    assert result is None


def test_dequeue_returns_task_and_moves_to_processing(pq, redis_mock):
    task = {"task_id": "t1", "payload": {"x": 1}, "priority": 2}
    redis_mock.zpopmin.return_value = [(json.dumps(task), 2e12 + 500.0)]
    result = pq.dequeue()
    assert result["task_id"] == "t1"
    assert result["payload"] == {"x": 1}
    assert redis_mock.zadd.called
    processing_key = redis_mock.zadd.call_args[0][0]
    assert "processing" in processing_key


def test_acknowledge_removes_from_processing(pq, redis_mock):
    task = {"task_id": "t1", "payload": {}, "priority": 2, "dequeued_at": 999.0}
    redis_mock.zrange.return_value = [json.dumps(task)]
    result = pq.acknowledge("t1")
    assert result is True
    redis_mock.zrem.assert_called_once()


def test_acknowledge_returns_false_when_not_found(pq, redis_mock):
    redis_mock.zrange.return_value = []
    result = pq.acknowledge("nonexistent")
    assert result is False


def test_depth_returns_pending_count(pq, redis_mock):
    redis_mock.zcard.return_value = 5
    assert pq.depth() == 5
    redis_mock.zcard.assert_called_with("test:pq:pending")


def test_depth_by_priority_groups_correctly(pq, redis_mock):
    tasks = [
        json.dumps({"task_id": "a", "payload": {}, "priority": 0}),
        json.dumps({"task_id": "b", "payload": {}, "priority": 0}),
        json.dumps({"task_id": "c", "payload": {}, "priority": 2}),
    ]
    redis_mock.zrange.return_value = tasks
    counts = pq.depth_by_priority()
    assert counts[PriorityQueue.PRIORITY_CRITICAL] == 2
    assert counts[PriorityQueue.PRIORITY_NORMAL] == 1
    assert counts[PriorityQueue.PRIORITY_HIGH] == 0
    assert counts[PriorityQueue.PRIORITY_LOW] == 0
