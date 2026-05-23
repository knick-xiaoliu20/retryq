import json
import time
import pytest
from unittest.mock import MagicMock, patch, call
from retryq.scheduler import Scheduler, DEFAULT_BACKOFF_BASE, DEFAULT_MAX_DELAY


@pytest.fixture
def redis_mock():
    return MagicMock()


@pytest.fixture
def scheduler(redis_mock):
    return Scheduler(redis_mock)


# --- compute_delay ---

def test_compute_delay_exponential(scheduler):
    assert scheduler.compute_delay(0) == 1   # 2^0
    assert scheduler.compute_delay(1) == 2   # 2^1
    assert scheduler.compute_delay(3) == 8   # 2^3


def test_compute_delay_capped_at_max(scheduler):
    assert scheduler.compute_delay(100) == DEFAULT_MAX_DELAY


def test_compute_delay_custom_base():
    s = Scheduler(MagicMock(), backoff_base=3, max_delay=100)
    assert s.compute_delay(2) == 9   # 3^2


# --- schedule_task ---

def test_schedule_task_calls_zadd(scheduler, redis_mock):
    task = {"id": "abc", "type": "email"}
    with patch("retryq.scheduler.time.time", return_value=1000.0):
        scheduler.schedule_task(task, attempt=2)

    expected_delay = DEFAULT_BACKOFF_BASE ** 2  # 4
    expected_score = 1000.0 + expected_delay
    payload = json.dumps({"id": "abc", "type": "email", "attempt": 2})
    redis_mock.zadd.assert_called_once_with(
        "retryq:scheduled", {payload: expected_score}
    )


def test_schedule_task_sets_attempt_on_task(scheduler, redis_mock):
    task = {"id": "xyz"}
    scheduler.schedule_task(task, attempt=5)
    assert task["attempt"] == 5


# --- promote_due_tasks ---

def test_promote_due_tasks_returns_zero_when_empty(scheduler, redis_mock):
    redis_mock.zrangebyscore.return_value = []
    result = scheduler.promote_due_tasks()
    assert result == 0
    redis_mock.pipeline.assert_not_called()


def test_promote_due_tasks_moves_items_to_pending(scheduler, redis_mock):
    raw1 = json.dumps({"id": "t1", "attempt": 1})
    raw2 = json.dumps({"id": "t2", "attempt": 2})
    redis_mock.zrangebyscore.return_value = [raw1, raw2]
    pipe = MagicMock()
    redis_mock.pipeline.return_value = pipe

    result = scheduler.promote_due_tasks()

    assert result == 2
    pipe.lpush.assert_any_call("retryq:pending", raw1)
    pipe.lpush.assert_any_call("retryq:pending", raw2)
    pipe.zrem.assert_any_call("retryq:scheduled", raw1)
    pipe.zrem.assert_any_call("retryq:scheduled", raw2)
    pipe.execute.assert_called_once()


# --- stop ---

def test_stop_sets_running_false(scheduler):
    scheduler._running = True
    scheduler.stop()
    assert scheduler._running is False
