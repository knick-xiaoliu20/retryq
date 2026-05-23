"""Worker subclass that integrates MetricsCollector for observability."""

import time
from typing import Callable, Optional

from retryq.queue import RetryQueue
from retryq.worker import Worker
from retryq.metrics import MetricsCollector


class InstrumentedWorker(Worker):
    """A Worker that records metrics for each task processed."""

    def __init__(
        self,
        queue: RetryQueue,
        handler: Callable[[dict], bool],
        metrics: Optional[MetricsCollector] = None,
        poll_interval: float = 1.0,
    ):
        super().__init__(queue, handler, poll_interval=poll_interval)
        self.metrics = metrics or MetricsCollector()
        self._queue_name = queue.name

    def process_one(self) -> bool:
        task = self.queue.dequeue()
        if task is None:
            return False

        self.metrics.record_dequeue(self._queue_name)
        start = self.metrics.start_timer()

        try:
            success = self.handler(task)
        except Exception:
            elapsed = self.metrics.elapsed(start)
            self.metrics.record_failure(self._queue_name, elapsed)
            self.queue.retry(task)
            self.metrics.record_retry(self._queue_name)
            return True

        elapsed = self.metrics.elapsed(start)

        if success:
            self.metrics.record_success(self._queue_name, elapsed)
        else:
            self.metrics.record_failure(self._queue_name, elapsed)
            self.queue.retry(task)
            self.metrics.record_retry(self._queue_name)

        return True

    def snapshot(self) -> dict:
        """Return current metrics snapshot for this worker's queue."""
        return self.metrics.snapshot(self._queue_name)
