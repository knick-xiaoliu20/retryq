import time
import pytest
from retryq.task_context import TaskContext


def make_ctx(**kwargs) -> TaskContext:
    defaults = dict(
        task_id="abc-123",
        task_type="send_email",
        payload={"to": "user@example.com"},
    )
    defaults.update(kwargs)
    return TaskContext(**defaults)


def test_defaults():
    ctx = make_ctx()
    assert ctx.attempt == 1
    assert ctx.max_attempts == 5
    assert ctx.last_error is None
    assert ctx.tags == {}


def test_is_final_attempt_false():
    ctx = make_ctx(attempt=3, max_attempts=5)
    assert not ctx.is_final_attempt


def test_is_final_attempt_true():
    ctx = make_ctx(attempt=5, max_attempts=5)
    assert ctx.is_final_attempt


def test_age_seconds_is_non_negative():
    ctx = make_ctx()
    assert ctx.age_seconds >= 0


def test_with_error_records_error():
    ctx = make_ctx()
    ctx2 = ctx.with_error("timeout")
    assert ctx2.last_error == "timeout"
    assert ctx2.task_id == ctx.task_id
    assert ctx.last_error is None  # original unchanged


def test_next_attempt_increments():
    ctx = make_ctx(attempt=2)
    ctx2 = ctx.next_attempt()
    assert ctx2.attempt == 3
    assert ctx.attempt == 2  # original unchanged


def test_to_dict_round_trip():
    ctx = make_ctx(attempt=2, tags={"env": "prod"})
    d = ctx.to_dict()
    ctx2 = TaskContext.from_dict(d)
    assert ctx2.task_id == ctx.task_id
    assert ctx2.attempt == ctx.attempt
    assert ctx2.tags == ctx.tags


def test_from_dict_defaults():
    ctx = TaskContext.from_dict(
        {"task_id": "x", "task_type": "t", "payload": {}}
    )
    assert ctx.attempt == 1
    assert ctx.max_attempts == 5
