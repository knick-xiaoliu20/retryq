import time
import logging
from typing import Callable, Dict, Any

from retryq.queue import RetryQueue

logger = logging.getLogger(__name__)


class Worker:
    """
    Processes tasks from a RetryQueue, retrying failures with backoff.
    """

    def __init__(
        self,
        queue: RetryQueue,
        handler: Callable[[Dict[str, Any]], None],
        poll_interval: float = 1.0,
    ):
        self.queue = queue
        self.handler = handler
        self.poll_interval = poll_interval
        self._running = False

    def process_one(self) -> bool:
        """
        Attempt to process a single task.
        Returns True if a task was processed (success or scheduled for retry).
        """
        self.queue.poll_scheduled()
        task = self.queue.dequeue()
        if task is None:
            return False

        task_id = task.get("task_id", "unknown")
        attempt = task.get("attempt", 0)
        logger.info("Processing task %s (attempt %d)", task_id, attempt)

        try:
            self.handler(task["payload"])
            logger.info("Task %s succeeded on attempt %d", task_id, attempt)
        except Exception as exc:
            logger.warning(
                "Task %s failed on attempt %d: %s", task_id, attempt, exc
            )
            scheduled = self.queue.retry(task)
            if not scheduled:
                logger.error(
                    "Task %s exceeded max retries and moved to dead queue", task_id
                )
        return True

    def run(self) -> None:
        """Run the worker loop until stop() is called."""
        self._running = True
        logger.info("Worker started")
        while self._running:
            processed = self.process_one()
            if not processed:
                time.sleep(self.poll_interval)
        logger.info("Worker stopped")

    def stop(self) -> None:
        """Signal the worker loop to stop."""
        self._running = False
