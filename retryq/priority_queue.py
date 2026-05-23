import json
import time
from typing import Optional


class PriorityQueue:
    """
    A priority-aware task queue backed by Redis sorted sets.
    Lower score = higher priority (processed first).
    Priority levels: 0 (critical), 1 (high), 2 (normal), 3 (low)
    """

    PRIORITY_CRITICAL = 0
    PRIORITY_HIGH = 1
    PRIORITY_NORMAL = 2
    PRIORITY_LOW = 3

    def __init__(self, redis_client, key_prefix: str = "retryq:pq"):
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.pending_key = f"{key_prefix}:pending"
        self.processing_key = f"{key_prefix}:processing"

    def _score(self, priority: int) -> float:
        """Compute score as priority * large_offset + timestamp for FIFO within same priority."""
        return priority * 1e12 + time.time()

    def enqueue(self, task_id: str, payload: dict, priority: int = PRIORITY_NORMAL) -> None:
        """Enqueue a task with a given priority."""
        if priority not in (self.PRIORITY_CRITICAL, self.PRIORITY_HIGH,
                            self.PRIORITY_NORMAL, self.PRIORITY_LOW):
            raise ValueError(f"Invalid priority: {priority}")
        data = json.dumps({"task_id": task_id, "payload": payload, "priority": priority})
        score = self._score(priority)
        self.redis.zadd(self.pending_key, {data: score})

    def dequeue(self) -> Optional[dict]:
        """Dequeue the highest-priority (lowest score) task atomically."""
        results = self.redis.zpopmin(self.pending_key, count=1)
        if not results:
            return None
        raw, score = results[0]
        task = json.loads(raw)
        processing_data = json.dumps({**task, "dequeued_at": time.time()})
        self.redis.zadd(self.processing_key, {processing_data: score})
        return task

    def acknowledge(self, task_id: str) -> bool:
        """Remove a task from the processing set after successful completion."""
        members = self.redis.zrange(self.processing_key, 0, -1)
        for raw in members:
            task = json.loads(raw)
            if task["task_id"] == task_id:
                self.redis.zrem(self.processing_key, raw)
                return True
        return False

    def depth(self) -> int:
        """Return the number of tasks currently pending."""
        return self.redis.zcard(self.pending_key)

    def depth_by_priority(self) -> dict:
        """Return counts of pending tasks grouped by priority level."""
        counts = {p: 0 for p in (self.PRIORITY_CRITICAL, self.PRIORITY_HIGH,
                                  self.PRIORITY_NORMAL, self.PRIORITY_LOW)}
        members = self.redis.zrange(self.pending_key, 0, -1)
        for raw in members:
            task = json.loads(raw)
            p = task.get("priority", self.PRIORITY_NORMAL)
            if p in counts:
                counts[p] += 1
        return counts
