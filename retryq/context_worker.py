from typing import Callable, Optional
from retryq.task_context import TaskContext
from retryq.context_middleware import ContextMiddlewareChain
from retryq.queue import RetryQueue
import json
import uuid


class ContextWorker:
    """Worker that wraps tasks in a TaskContext and runs them through
    a middleware chain before dispatching to a handler.
    """

    def __init__(
        self,
        queue: RetryQueue,
        handler: Callable[[TaskContext], bool],
        middleware_chain: Optional[ContextMiddlewareChain] = None,
    ) -> None:
        self._queue = queue
        self._handler = handler
        self._chain = middleware_chain or ContextMiddlewareChain()
        self._running = False

    # ------------------------------------------------------------------
    def use(self, middleware) -> "ContextWorker":
        """Register a middleware on the internal chain."""
        self._chain.use(middleware)
        return self

    # ------------------------------------------------------------------
    def process_one(self) -> bool:
        """Dequeue one task, wrap it in a TaskContext, run the chain.

        Returns True if a task was processed, False otherwise.
        """
        raw = self._queue.dequeue()
        if raw is None:
            return False

        try:
            data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        except (json.JSONDecodeError, TypeError):
            data = {"payload": raw}

        ctx = TaskContext(
            task_id=data.get("task_id", str(uuid.uuid4())),
            task_type=data.get("task_type", "unknown"),
            payload=data.get("payload", data),
            attempt=data.get("attempt", 1),
            max_attempts=data.get("max_attempts", 5),
            enqueued_at=data.get("enqueued_at", __import__("time").time()),
            last_error=data.get("last_error"),
            tags=data.get("tags", {}),
        )

        result = self._chain.execute(ctx, self._handler)
        if result:
            self._queue.acknowledge(raw)
        return True

    # ------------------------------------------------------------------
    def run(self) -> None:
        import time

        self._running = True
        while self._running:
            if not self.process_one():
                time.sleep(0.1)

    def stop(self) -> None:
        self._running = False
