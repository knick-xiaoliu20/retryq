"""Dead letter queue for tasks that have exhausted all retry attempts."""

import json
import time
from typing import Optional

DEAD_LETTER_KEY = "retryq:dead_letter"
DEAD_LETTER_META_KEY = "retryq:dead_letter:meta"


class DeadLetterQueue:
    """Stores tasks that have exceeded their maximum retry attempts."""

    def __init__(self, redis_client, max_dead_tasks: int = 1000):
        self.redis = redis_client
        self.max_dead_tasks = max_dead_tasks

    def push(self, task: dict, reason: str = "max_retries_exceeded") -> None:
        """Push a failed task into the dead letter queue."""
        entry = {
            "task": task,
            "reason": reason,
            "dead_at": time.time(),
        }
        serialized = json.dumps(entry)
        pipe = self.redis.pipeline()
        pipe.lpush(DEAD_LETTER_KEY, serialized)
        pipe.ltrim(DEAD_LETTER_KEY, 0, self.max_dead_tasks - 1)
        pipe.hincrby(DEAD_LETTER_META_KEY, "total_dead", 1)
        pipe.execute()

    def pop(self) -> Optional[dict]:
        """Pop the most recent dead task from the queue."""
        raw = self.redis.lpop(DEAD_LETTER_KEY)
        if raw is None:
            return None
        return json.loads(raw)

    def peek(self, count: int = 10) -> list:
        """Return up to `count` recent dead tasks without removing them."""
        items = self.redis.lrange(DEAD_LETTER_KEY, 0, count - 1)
        return [json.loads(item) for item in items]

    def size(self) -> int:
        """Return the number of tasks currently in the dead letter queue."""
        return self.redis.llen(DEAD_LETTER_KEY)

    def total_dead(self) -> int:
        """Return the all-time count of tasks that have been dead-lettered."""
        val = self.redis.hget(DEAD_LETTER_META_KEY, "total_dead")
        return int(val) if val else 0

    def flush(self) -> int:
        """Remove all entries from the dead letter queue. Returns count removed."""
        count = self.size()
        self.redis.delete(DEAD_LETTER_KEY)
        return count
