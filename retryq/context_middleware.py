from typing import Callable, List, Optional
from retryq.task_context import TaskContext


MiddlewareFn = Callable[[TaskContext, Callable[[TaskContext], bool]], bool]


class ContextMiddlewareChain:
    """Chains middleware functions around a task handler.

    Each middleware receives the context and a `next` callable that
    invokes the remainder of the chain.  The final `next` calls the
    actual handler.
    """

    def __init__(self) -> None:
        self._middlewares: List[MiddlewareFn] = []

    def use(self, middleware: MiddlewareFn) -> "ContextMiddlewareChain":
        """Register a middleware function and return self for chaining."""
        self._middlewares.append(middleware)
        return self

    def execute(
        self,
        context: TaskContext,
        handler: Callable[[TaskContext], bool],
    ) -> bool:
        """Execute the middleware chain followed by the handler."""
        chain = list(self._middlewares)

        def build_next(index: int) -> Callable[[TaskContext], bool]:
            if index >= len(chain):
                return handler

            def next_fn(ctx: TaskContext) -> bool:
                return chain[index](ctx, build_next(index + 1))

            return next_fn

        return build_next(0)(context)


# ---------------------------------------------------------------------------
# Built-in middleware helpers
# ---------------------------------------------------------------------------


def logging_middleware(
    log_fn: Optional[Callable[[str], None]] = None,
) -> MiddlewareFn:
    """Middleware that logs task start and completion."""
    _log = log_fn or print

    def middleware(ctx: TaskContext, next_fn: Callable[[TaskContext], bool]) -> bool:
        _log(f"[retryq] start task_id={ctx.task_id} type={ctx.task_type} attempt={ctx.attempt}")
        result = next_fn(ctx)
        status = "ok" if result else "failed"
        _log(f"[retryq] done  task_id={ctx.task_id} status={status}")
        return result

    return middleware


def tag_injector_middleware(tags: dict) -> MiddlewareFn:
    """Middleware that merges static tags into every context."""

    def middleware(ctx: TaskContext, next_fn: Callable[[TaskContext], bool]) -> bool:
        ctx.tags.update(tags)
        return next_fn(ctx)

    return middleware
