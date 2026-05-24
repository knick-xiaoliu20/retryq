"""Task router that dispatches tasks to handlers based on task type."""

from typing import Callable, Dict, Optional, Any


class RouteNotFoundError(Exception):
    """Raised when no handler is registered for a given task type."""
    pass


class TaskRouter:
    """Routes tasks to registered handlers based on task type.

    Allows registering multiple handlers, one per task type, and
    dispatching tasks to the appropriate handler at runtime.

    Example::

        router = TaskRouter()

        @router.route("send_email")
        def handle_email(payload):
            ...

        router.dispatch({"type": "send_email", "payload": {...}})
    """

    def __init__(self, default_handler: Optional[Callable] = None) -> None:
        self._routes: Dict[str, Callable] = {}
        self._default_handler = default_handler

    def route(self, task_type: str) -> Callable:
        """Decorator to register a handler for a specific task type."""
        if not task_type or not isinstance(task_type, str):
            raise ValueError("task_type must be a non-empty string")

        def decorator(fn: Callable) -> Callable:
            self._routes[task_type] = fn
            return fn

        return decorator

    def register(self, task_type: str, handler: Callable) -> None:
        """Explicitly register a handler for a task type."""
        if not task_type or not isinstance(task_type, str):
            raise ValueError("task_type must be a non-empty string")
        if not callable(handler):
            raise TypeError("handler must be callable")
        self._routes[task_type] = handler

    def dispatch(self, task: Dict[str, Any]) -> Any:
        """Dispatch a task to its registered handler.

        Args:
            task: A dict with at least a ``type`` key.

        Returns:
            Whatever the handler returns.

        Raises:
            RouteNotFoundError: If no handler is registered and no default
                handler was provided.
        """
        task_type = task.get("type")
        handler = self._routes.get(task_type) or self._default_handler
        if handler is None:
            raise RouteNotFoundError(
                f"No handler registered for task type: {task_type!r}"
            )
        return handler(task)

    def registered_types(self) -> list:
        """Return a list of all registered task types."""
        return list(self._routes.keys())

    def has_route(self, task_type: str) -> bool:
        """Return True if a handler is registered for the given task type."""
        return task_type in self._routes
