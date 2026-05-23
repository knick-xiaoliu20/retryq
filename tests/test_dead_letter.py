"""Tests for the DeadLetterQueue and its integration with RetryQueue."""

import json
import pytest
from unittest.mock import MagicMock, patch

from retryq.dead_letter import DeadLetterQueue, DEAD_LETTER_KEY, DEAD_LETTER_META_KEY
from retryq.queue import RetryQueue


@pytest.fixture
def redis_mock():
    mock = MagicMock()
    mock.pipeline.return_value.__enter__ = MagicMock(return_value=mock.pipeline.return_value)
    mock.pipeline.return_value.__exit__ = MagicMock(return_value=False)
    mock.pipeline.return_value.execute = MagicMock(return_value=[1, 1, 1])
    return mock


@pytest.fixture
def dlq(redis_mock):
    return DeadLetterQueue(redis_mock, max_dead_tasks=100)


def test_push_serializes_task(dlq, redis_mock):
    task = {"id": "t1", "payload": {"x": 1}, "attempts": 5}
    dlq.push(task, reason="max_retries_exceeded")
    pipe = redis_mock.pipeline.return_value
    pipe.lpush.assert_called_once()
    args = pipe.lpush.call_args[0]
    assert args[0] == DEAD_LETTER_KEY
    entry = json.loads(args[1])
    assert entry["task"] == task
    assert entry["reason"] == "max_retries_exceeded"
    assert "dead_at" in entry


def test_push_trims_to_max(dlq, redis_mock):
    task = {"id": "t2", "payload": {}}
    dlq.push(task)
    pipe = redis_mock.pipeline.return_value
    pipe.ltrim.assert_called_once_with(DEAD_LETTER_KEY, 0, 99)


def test_push_default_reason(dlq, redis_mock):
    """Verify that push uses a default reason when none is provided."""
    task = {"id": "t_default", "payload": {}}
    dlq.push(task)
    pipe = redis_mock.pipeline.return_value
    args = pipe.lpush.call_args[0]
    entry = json.loads(args[1])
    assert "reason" in entry
    assert entry["reason"] is not None


def test_pop_returns_none_when_empty(dlq, redis_mock):
    redis_mock.lpop.return_value = None
    assert dlq.pop() is None


def test_pop_returns_parsed_entry(dlq, redis_mock):
    entry = {"task": {"id": "t3"}, "reason": "test", "dead_at": 1234.0}
    redis_mock.lpop.return_value = json.dumps(entry)
    result = dlq.pop()
    assert result == entry


def test_peek_returns_list(dlq, redis_mock):
    entries = [{"task": {"id": f"t{i}"}, "reason": "r", "dead_at": 0.0} for i in range(3)]
    redis_mock.lrange.return_value = [json.dumps(e) for e in entries]
    result = dlq.peek(count=3)
    assert len(result) == 3
    assert result[0]["task"]["id"] == "t0"


def test_size(dlq, redis_mock):
    redis_mock.llen.return_value = 42
    assert dlq.size() == 42


def test_total_dead(dlq, redis_mock):
    redis_mock.hget.return_value = b"7"
    assert dlq.total_dead() == 7


def test_total_dead_when_none(dlq, redis_mock):
    redis_mock.hget.return_value = None
    assert dlq.total_dead() == 0


def test_flush_returns_count(dlq, redis_mock):
    redis_mock.llen.return_value = 5
    count = dlq.flush()
    assert count == 5
    redis_mock.delete.assert_called_once_with(DEAD_LETTER_KEY)


def test_retry_queue_sends_to_dlq_on_max_retries(redis_mock):
    dlq = MagicMock(spec=DeadLetterQueue)
    q = RetryQueue(redis_mock, max_retries=2, dead_letter=dlq)
    task = {"id": "t9", "payload": {}, "attempts": 2}
    result = q.retry(task, delay=0)
    assert result is False
    dlq.push.assert_called_once()
    pushed_task = dlq.push.call_args[0][0]
    assert pushed_task["attempts"] == 3
