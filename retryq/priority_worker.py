import time
import logging
from typing import Callable, Optional
from retryq.priority_queue import PriorityQueue

logger = logging.getLogger(__name__)


class PriorityWorker:
    """
    Worker that processes tasks from a PriorityQueue, respecting priority order.
    Supports per-priority handlers and a fallback default handler.
    """

    def __init__(
        self,
        queue: PriorityQueue,
        default_handler: Callable[[dict], None],
        poll_interval: float = 1.0,
    ):
        self.queue = queue
        self.default_handler = default_handler
        self.poll_interval = poll_interval
        self._running = False
        self._priority_handlers: dict[int, Callable[[dict], None]] = {}

    def register_handler(self, priority: int, handler: Callable[[dict], None]) -> None:
        """Register a handler specific to a priority level."""
        self._priority_handlers[priority] = handler

    def _get_handler(self, priority: int) -> Callable[[dict], None]:
        return self._priority_handlers.get(priority, self.default_handler)

    def process_one(self) -> bool:
        """Attempt to process a single task. Returns True if a task was processed."""
        task = self.queue.dequeue()
        if task is None:
            return False

        task_id = task.get("task_id", "unknown")
        priority = task.get("priority", PriorityQueue.PRIORITY_NORMAL)
        handler = self._get_handler(priority)

        try:
            handler(task)
            self.queue.acknowledge(task_id)
            logger.info("Task %s (priority=%d) completed.", task_id, priority)
        except Exception as exc:
            logger.error("Task %s failed: %s", task_id, exc)
            raise

        return True

    def run(self) -> None:
        """Run the worker loop until stop() is called."""
        self._running = True
        logger.info("PriorityWorker started.")
        while self._running:
            processed = self.process_one()
            if not processed:
                time.sleep(self.poll_interval)
        logger.info("PriorityWorker stopped.")

    def stop(self) -> None:
        """Signal the worker loop to exit."""
        self._running = False
