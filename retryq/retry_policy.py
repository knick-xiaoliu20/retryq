from dataclasses import dataclass, field
from typing import Optional, Type, Tuple


@dataclass
class RetryPolicy:
    """Defines retry behaviour for tasks in the queue."""

    max_attempts: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = False
    retryable_exceptions: Tuple[Type[Exception], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be positive")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if self.backoff_factor < 1.0:
            raise ValueError("backoff_factor must be >= 1.0")

    def compute_delay(self, attempt: int) -> float:
        """Return delay in seconds for the given attempt number (1-indexed)."""
        import random

        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = random.uniform(0, delay)
        return delay

    def should_retry(self, attempt: int, exc: Optional[Exception] = None) -> bool:
        """Return True if the task should be retried given the current attempt."""
        if attempt >= self.max_attempts:
            return False
        if exc is not None and self.retryable_exceptions:
            return isinstance(exc, self.retryable_exceptions)
        return True

    @classmethod
    def from_dict(cls, data: dict) -> "RetryPolicy":
        retryable = tuple(data.pop("retryable_exceptions", []))
        return cls(**data, retryable_exceptions=retryable)

    def to_dict(self) -> dict:
        return {
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "backoff_factor": self.backoff_factor,
            "jitter": self.jitter,
        }
