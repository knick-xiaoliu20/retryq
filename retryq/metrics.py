"""Metrics collection for RetryQueue operations."""

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class QueueMetrics:
    enqueued: int = 0
    dequeued: int = 0
    retried: int = 0
    failed: int = 0
    succeeded: int = 0
    total_processing_time: float = 0.0
    _processing_start: Optional[float] = field(default=None, repr=False)

    @property
    def avg_processing_time(self) -> float:
        total = self.succeeded + self.failed
        if total == 0:
            return 0.0
        return self.total_processing_time / total

    def to_dict(self) -> Dict[str, float]:
        return {
            "enqueued": self.enqueued,
            "dequeued": self.dequeued,
            "retried": self.retried,
            "failed": self.failed,
            "succeeded": self.succeeded,
            "avg_processing_time": self.avg_processing_time,
        }


class MetricsCollector:
    """Collects and exposes runtime metrics for the retry queue."""

    def __init__(self):
        self._metrics: Dict[str, QueueMetrics] = {}

    def _get(self, queue_name: str) -> QueueMetrics:
        if queue_name not in self._metrics:
            self._metrics[queue_name] = QueueMetrics()
        return self._metrics[queue_name]

    def record_enqueue(self, queue_name: str) -> None:
        self._get(queue_name).enqueued += 1

    def record_dequeue(self, queue_name: str) -> None:
        self._get(queue_name).dequeued += 1

    def record_retry(self, queue_name: str) -> None:
        self._get(queue_name).retried += 1

    def record_failure(self, queue_name: str, elapsed: float) -> None:
        m = self._get(queue_name)
        m.failed += 1
        m.total_processing_time += elapsed

    def record_success(self, queue_name: str, elapsed: float) -> None:
        m = self._get(queue_name)
        m.succeeded += 1
        m.total_processing_time += elapsed

    def start_timer(self) -> float:
        return time.monotonic()

    def elapsed(self, start: float) -> float:
        return time.monotonic() - start

    def snapshot(self, queue_name: str) -> Dict[str, float]:
        return self._get(queue_name).to_dict()

    def all_snapshots(self) -> Dict[str, Dict[str, float]]:
        return {name: m.to_dict() for name, m in self._metrics.items()}

    def reset(self, queue_name: str) -> None:
        self._metrics.pop(queue_name, None)
