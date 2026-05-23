"""Tests for InstrumentedWorker metrics integration."""

import pytest
from unittest.mock import MagicMock, patch
from retryq.instrumented_worker import InstrumentedWorker
from retryq.metrics import MetricsCollector


@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.name = "test_queue"
    return q


@pytest.fixture
def metrics():
    return MetricsCollector()


@pytest.fixture
def worker(mock_queue, metrics):
    handler = MagicMock(return_value=True)
    w = InstrumentedWorker(mock_queue, handler, metrics=metrics)
    return w


def test_process_one_no_task_records_nothing(worker, mock_queue, metrics):
    mock_queue.dequeue.return_value = None
    result = worker.process_one()
    assert result is False
    snap = metrics.snapshot("test_queue")
    assert snap["dequeued"] == 0


def test_process_one_success_records_dequeue_and_success(worker, mock_queue, metrics):
    task = {"id": "abc", "payload": {}}
    mock_queue.dequeue.return_value = task
    worker.handler.return_value = True

    result = worker.process_one()

    assert result is True
    snap = metrics.snapshot("test_queue")
    assert snap["dequeued"] == 1
    assert snap["succeeded"] == 1
    assert snap["failed"] == 0
    assert snap["retried"] == 0


def test_process_one_failure_records_retry(worker, mock_queue, metrics):
    task = {"id": "xyz", "payload": {}}
    mock_queue.dequeue.return_value = task
    worker.handler.return_value = False

    result = worker.process_one()

    assert result is True
    snap = metrics.snapshot("test_queue")
    assert snap["dequeued"] == 1
    assert snap["failed"] == 1
    assert snap["retried"] == 1
    mock_queue.retry.assert_called_once_with(task)


def test_process_one_exception_records_failure_and_retry(worker, mock_queue, metrics):
    task = {"id": "err", "payload": {}}
    mock_queue.dequeue.return_value = task
    worker.handler.side_effect = RuntimeError("boom")

    result = worker.process_one()

    assert result is True
    snap = metrics.snapshot("test_queue")
    assert snap["failed"] == 1
    assert snap["retried"] == 1
    mock_queue.retry.assert_called_once_with(task)


def test_snapshot_returns_metrics_dict(worker, mock_queue, metrics):
    mock_queue.dequeue.return_value = None
    snap = worker.snapshot()
    assert "enqueued" in snap
    assert "succeeded" in snap
    assert "avg_processing_time" in snap


def test_default_metrics_created_if_not_provided(mock_queue):
    handler = MagicMock(return_value=True)
    w = InstrumentedWorker(mock_queue, handler)
    assert isinstance(w.metrics, MetricsCollector)
