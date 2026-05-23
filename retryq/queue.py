import time
import json
import redis
from typing import Any, Dict, Optional

DEFAULT_MAX_RETRIES = 5
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_BACKOFF_FACTOR = 2.0


class RetryQueue:
    """
    A simple task retry queue with exponential backoff backed by Redis.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        queue_name: str = "retryq",
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    ):
        self.redis = redis_client
        self.queue_name = queue_name
        self.pending_key = f"{queue_name}:pending"
        self.scheduled_key = f"{queue_name}:scheduled"
        self.dead_key = f"{queue_name}:dead"
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor

    def enqueue(self, task_id: str, payload: Dict[str, Any]) -> None:
        """Push a new task onto the pending queue."""
        task = {
            "task_id": task_id,
            "payload": payload,
            "attempt": 0,
        }
        self.redis.rpush(self.pending_key, json.dumps(task))

    def dequeue(self) -> Optional[Dict[str, Any]]:
        """Pop the next task from the pending queue."""
        raw = self.redis.lpop(self.pending_key)
        if raw is None:
            return None
        return json.loads(raw)

    def retry(self, task: Dict[str, Any]) -> bool:
        """
        Schedule a task for retry with exponential backoff.
        Returns False if max retries exceeded (task moved to dead queue).
        """
        attempt = task.get("attempt", 0) + 1
        if attempt > self.max_retries:
            self.redis.rpush(self.dead_key, json.dumps(task))
            return False

        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        run_at = time.time() + delay
        task["attempt"] = attempt
        self.redis.zadd(self.scheduled_key, {json.dumps(task): run_at})
        return True

    def poll_scheduled(self) -> int:
        """Move due scheduled tasks back to the pending queue. Returns count moved."""
        now = time.time()
        due_tasks = self.redis.zrangebyscore(self.scheduled_key, "-inf", now)
        if not due_tasks:
            return 0
        pipe = self.redis.pipeline()
        for raw in due_tasks:
            pipe.zrem(self.scheduled_key, raw)
            pipe.rpush(self.pending_key, raw)
        pipe.execute()
        return len(due_tasks)

    def queue_lengths(self) -> Dict[str, int]:
        """Return current lengths of pending, scheduled, and dead queues."""
        return {
            "pending": self.redis.llen(self.pending_key),
            "scheduled": self.redis.zcard(self.scheduled_key),
            "dead": self.redis.llen(self.dead_key),
        }
