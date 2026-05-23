"""Core retry queue built on Redis."""

import json
import time
from typing import Optional

from retryq.dead_letter import DeadLetterQueue

PENDING_KEY = "retryq:pending"
PROCESSING_KEY = "retryq:processing"


class RetryQueue:
    """Simple task queue with exponential-backoff retry support."""

    def __init__(self, redis_client, max_retries: int = 5, dead_letter: Optional[DeadLetterQueue] = None):
        self.redis = redis_client
        self.max_retries = max_retries
        self.dead_letter = dead_letter

    def enqueue(self, task_id: str, payload: dict, priority: float = None) -> None:
        """Push a new task onto the pending queue."""
        task = {
            "id": task_id,
            "payload": payload,
            "attempts": 0,
            "enqueued_at": time.time(),
        }
        score = priority if priority is not None else time.time()
        self.redis.zadd(PENDING_KEY, {json.dumps(task): score})

    def dequeue(self) -> Optional[dict]:
        """Pop the highest-priority task from the pending queue."""
        results = self.redis.zpopmin(PENDING_KEY, 1)
        if not results:
            return None
        raw, _ = results[0]
        task = json.loads(raw)
        self.redis.hset(PROCESSING_KEY, task["id"], json.dumps(task))
        return task

    def acknowledge(self, task_id: str) -> None:
        """Mark a task as successfully completed."""
        self.redis.hdel(PROCESSING_KEY, task_id)

    def retry(self, task: dict, delay: float = 0.0) -> bool:
        """Re-enqueue a task for retry. Returns False if max retries exceeded."""
        task = dict(task)
        task["attempts"] = task.get("attempts", 0) + 1

        if task["attempts"] > self.max_retries:
            self.redis.hdel(PROCESSING_KEY, task["id"])
            if self.dead_letter is not None:
                self.dead_letter.push(task, reason="max_retries_exceeded")
            return False

        score = time.time() + delay
        self.redis.hdel(PROCESSING_KEY, task["id"])
        self.redis.zadd(PENDING_KEY, {json.dumps(task): score})
        return True

    def pending_count(self) -> int:
        return self.redis.zcard(PENDING_KEY)

    def processing_count(self) -> int:
        return self.redis.hlen(PROCESSING_KEY)
