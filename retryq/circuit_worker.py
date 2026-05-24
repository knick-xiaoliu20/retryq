from typing import Callable, Optional
from retryq.worker import Worker
from retryq.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState


class CircuitBreakerOpenError(Exception):
    """Raised when a task is attempted while the circuit is open."""


class CircuitWorker(Worker):
    """
    A Worker that wraps task processing with a CircuitBreaker.
    If the circuit is open, task processing is skipped until recovery.
    """

    def __init__(
        self,
        queue,
        handler: Callable,
        breaker: Optional[CircuitBreaker] = None,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        super().__init__(queue, handler)
        if breaker is not None:
            self.breaker = breaker
        else:
            self.breaker = CircuitBreaker(config or CircuitBreakerConfig())

    def process_one(self) -> bool:
        if not self.breaker.allow_request():
            return False

        task = self.queue.dequeue()
        if task is None:
            return False

        if self.breaker.state == CircuitState.HALF_OPEN:
            self.breaker._half_open_calls += 1

        try:
            self.handler(task)
            self.queue.acknowledge(task["id"])
            self.breaker.record_success()
            return True
        except Exception:
            self.breaker.record_failure()
            self.queue.requeue(task)
            return False

    @property
    def circuit_state(self) -> CircuitState:
        return self.breaker.state
