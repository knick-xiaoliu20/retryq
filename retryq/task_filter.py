from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional


class FilterRejectedError(Exception):
    """Raised when a task is rejected by a filter."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class TaskFilter:
    """Composable filter chain evaluated before task processing.

    Filters are callables that accept a task dict and return True to
    allow the task or False (or raise FilterRejectedError) to reject it.
    """

    _filters: List[Callable[[Dict[str, Any]], bool]] = field(
        default_factory=list, init=False, repr=False
    )

    def add(self, fn: Callable[[Dict[str, Any]], bool]) -> "TaskFilter":
        """Register a filter function and return self for chaining."""
        self._filters.append(fn)
        return self

    def allow_types(self, *task_types: str) -> "TaskFilter":
        """Only allow tasks whose 'type' matches one of the given patterns (glob)."""

        def _check(task: Dict[str, Any]) -> bool:
            task_type = task.get("type", "")
            if not any(fnmatch.fnmatch(task_type, pat) for pat in task_types):
                raise FilterRejectedError(
                    f"task type '{task_type}' not in allowed types {task_types}"
                )
            return True

        return self.add(_check)

    def require_fields(self, *fields: str) -> "TaskFilter":
        """Reject tasks that are missing any of the specified payload fields."""

        def _check(task: Dict[str, Any]) -> bool:
            payload = task.get("payload", {})
            missing = [f for f in fields if f not in payload]
            if missing:
                raise FilterRejectedError(
                    f"task missing required fields: {missing}"
                )
            return True

        return self.add(_check)

    def max_attempts(self, limit: int) -> "TaskFilter":
        """Reject tasks that have exceeded the maximum attempt count."""

        def _check(task: Dict[str, Any]) -> bool:
            attempts = int(task.get("attempts", 0))
            if attempts >= limit:
                raise FilterRejectedError(
                    f"task exceeded max attempts: {attempts} >= {limit}"
                )
            return True

        return self.add(_check)

    def evaluate(self, task: Dict[str, Any]) -> bool:
        """Run all filters against *task*.

        Returns True if every filter passes.
        Raises FilterRejectedError on the first rejection.
        """
        for fn in self._filters:
            fn(task)  # raises FilterRejectedError on failure
        return True
