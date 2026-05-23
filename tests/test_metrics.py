"""Tests for MetricsCollector."""

import time
import pytest
from retryq.metrics import MetricsCollector, QueueMetrics


@pytest.fixture
def collector():
    return MetricsCollector()


def test_initial_snapshot_is_zero(collector):
    snap = collector.snapshot("default")
    assert snap["enqueued"] == 0
    assert snap["dequeued"] == 0
    assert snap["retried"] == 0
    assert snap["failed"] == 0
    assert snap["succeeded"] == 0
    assert snap["avg_processing_time"] == 0.0


def test_record_enqueue(collector):
    collector.record_enqueue("default")
    collector.record_enqueue("default")
    assert collector.snapshot("default")["enqueued"] == 2


def test_record_dequeue(collector):
    collector.record_dequeue("jobs")
    assert collector.snapshot("jobs")["dequeued"] == 1


def test_record_retry(collector):
    collector.record_retry("default")
    collector.record_retry("default")
    collector.record_retry("default")
    assert collector.snapshot("default")["retried"] == 3


def test_record_success_updates_avg(collector):
    collector.record_success("default", 0.5)
    collector.record_success("default", 1.5)
    snap = collector.snapshot("default")
    assert snap["succeeded"] == 2
    assert snap["avg_processing_time"] == pytest.approx(1.0)


def test_record_failure_updates_avg(collector):
    collector.record_failure("default", 2.0)
    snap = collector.snapshot("default")
    assert snap["failed"] == 1
    assert snap["avg_processing_time"] == pytest.approx(2.0)


def test_avg_processing_time_mixed(collector):
    collector.record_success("q", 1.0)
    collector.record_failure("q", 3.0)
    snap = collector.snapshot("q")
    assert snap["avg_processing_time"] == pytest.approx(2.0)


def test_multiple_queues_isolated(collector):
    collector.record_enqueue("q1")
    collector.record_enqueue("q1")
    collector.record_enqueue("q2")
    assert collector.snapshot("q1")["enqueued"] == 2
    assert collector.snapshot("q2")["enqueued"] == 1


def test_all_snapshots(collector):
    collector.record_enqueue("a")
    collector.record_enqueue("b")
    all_snaps = collector.all_snapshots()
    assert "a" in all_snaps
    assert "b" in all_snaps


def test_reset_clears_metrics(collector):
    collector.record_enqueue("default")
    collector.reset("default")
    assert collector.snapshot("default")["enqueued"] == 0


def test_timer_elapsed(collector):
    start = collector.start_timer()
    time.sleep(0.05)
    elapsed = collector.elapsed(start)
    assert elapsed >= 0.04
