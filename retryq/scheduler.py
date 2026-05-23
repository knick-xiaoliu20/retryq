import time
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_BACKOFF_BASE = 2
DEFAULT_MAX_DELAY = 3600  # 1 hour cap


class Scheduler:
    """
    Polls Redis sorted set for tasks whose retry time has arrived
    and moves them back to the pending queue.
    """

    def __init__(self, redis_client, pending_key: str = "retryq:pending",
                 scheduled_key: str = "retryq:scheduled",
                 backoff_base: int = DEFAULT_BACKOFF_BASE,
                 max_delay: int = DEFAULT_MAX_DELAY):
        self.redis = redis_client
        self.pending_key = pending_key
        self.scheduled_key = scheduled_key
        self.backoff_base = backoff_base
        self.max_delay = max_delay
        self._running = False

    def compute_delay(self, attempt: int) -> float:
        """Exponential backoff: base^attempt, capped at max_delay."""
        delay = self.backoff_base ** attempt
        return min(delay, self.max_delay)

    def schedule_task(self, task: dict, attempt: int) -> None:
        """Add a task to the scheduled sorted set with a future score."""
        delay = self.compute_delay(attempt)
        run_at = time.time() + delay
        task["attempt"] = attempt
        payload = json.dumps(task)
        self.redis.zadd(self.scheduled_key, {payload: run_at})
        logger.debug("Scheduled task %s for %.1fs from now (attempt %d)",
                     task.get("id"), delay, attempt)

    def promote_due_tasks(self) -> int:
        """Move all due tasks from scheduled set into the pending list."""
        now = time.time()
        due = self.redis.zrangebyscore(self.scheduled_key, "-inf", now)
        if not due:
            return 0

        pipe = self.redis.pipeline()
        for raw in due:
            pipe.lpush(self.pending_key, raw)
            pipe.zrem(self.scheduled_key, raw)
        pipe.execute()

        logger.info("Promoted %d due task(s) to pending", len(due))
        return len(due)

    def run(self, poll_interval: float = 1.0) -> None:
        """Continuously promote due tasks until stopped."""
        self._running = True
        logger.info("Scheduler started (poll_interval=%.1fs)", poll_interval)
        while self._running:
            try:
                self.promote_due_tasks()
            except Exception as exc:  # pragma: no cover
                logger.error("Scheduler error: %s", exc)
            time.sleep(poll_interval)

    def stop(self) -> None:
        """Signal the run loop to exit."""
        self._running = False
        logger.info("Scheduler stopping")
