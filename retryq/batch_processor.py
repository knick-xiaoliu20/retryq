import time
from typing import Callable, List, Optional
from retryq.queue import RetryQueue
from retryq.metrics import MetricsCollector


class BatchProcessor:
    """
    Processes multiple tasks from a RetryQueue in a single batch.
    Supports configurable batch size, timeout, and optional metrics collection.
    """

    def __init__(
        self,
        queue: RetryQueue,
        handler: Callable[[dict], bool],
        batch_size: int = 10,
        batch_timeout: float = 5.0,
        metrics: Optional[MetricsCollector] = None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if batch_timeout <= 0:
            raise ValueError("batch_timeout must be positive")

        self.queue = queue
        self.handler = handler
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.metrics = metrics
        self._running = False

    def collect_batch(self) -> List[dict]:
        """Dequeue up to batch_size tasks within batch_timeout seconds."""
        tasks = []
        deadline = time.monotonic() + self.batch_timeout
        while len(tasks) < self.batch_size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            task = self.queue.dequeue(timeout=int(remaining) or 1)
            if task is None:
                break
            tasks.append(task)
        return tasks

    def process_batch(self) -> dict:
        """Collect and process a batch of tasks. Returns summary stats."""
        tasks = self.collect_batch()
        succeeded, failed = 0, 0

        for task in tasks:
            if self.metrics:
                self.metrics.record_dequeue()
            try:
                ok = self.handler(task)
            except Exception:
                ok = False

            if ok:
                self.queue.acknowledge(task)
                succeeded += 1
                if self.metrics:
                    self.metrics.record_success()
            else:
                self.queue.requeue(task)
                failed += 1
                if self.metrics:
                    self.metrics.record_retry()

        return {"processed": len(tasks), "succeeded": succeeded, "failed": failed}

    def run(self, max_batches: Optional[int] = None) -> None:
        """Run the batch processor loop."""
        self._running = True
        batches = 0
        while self._running:
            self.process_batch()
            batches += 1
            if max_batches is not None and batches >= max_batches:
                break

    def stop(self) -> None:
        """Signal the processor to stop after the current batch."""
        self._running = False
