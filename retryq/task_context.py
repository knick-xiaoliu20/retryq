from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time


@dataclass
class TaskContext:
    """Carries metadata about a task during processing."""

    task_id: str
    task_type: str
    payload: Dict[str, Any]
    attempt: int = 1
    max_attempts: int = 5
    enqueued_at: float = field(default_factory=time.time)
    last_error: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def is_final_attempt(self) -> bool:
        return self.attempt >= self.max_attempts

    @property
    def age_seconds(self) -> float:
        return time.time() - self.enqueued_at

    def with_error(self, error: str) -> "TaskContext":
        """Return a copy of this context with the given error recorded."""
        return TaskContext(
            task_id=self.task_id,
            task_type=self.task_type,
            payload=self.payload,
            attempt=self.attempt,
            max_attempts=self.max_attempts,
            enqueued_at=self.enqueued_at,
            last_error=error,
            tags=self.tags,
        )

    def next_attempt(self) -> "TaskContext":
        """Return a copy of this context with attempt incremented."""
        return TaskContext(
            task_id=self.task_id,
            task_type=self.task_type,
            payload=self.payload,
            attempt=self.attempt + 1,
            max_attempts=self.max_attempts,
            enqueued_at=self.enqueued_at,
            last_error=self.last_error,
            tags=self.tags,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "enqueued_at": self.enqueued_at,
            "last_error": self.last_error,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            payload=data["payload"],
            attempt=data.get("attempt", 1),
            max_attempts=data.get("max_attempts", 5),
            enqueued_at=data.get("enqueued_at", time.time()),
            last_error=data.get("last_error"),
            tags=data.get("tags", {}),
        )
