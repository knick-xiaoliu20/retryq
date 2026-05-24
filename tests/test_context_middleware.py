import pytest
from retryq.task_context import TaskContext
from retryq.context_middleware import (
    ContextMiddlewareChain,
    logging_middleware,
    tag_injector_middleware,
)


def make_ctx() -> TaskContext:
    return TaskContext(
        task_id="t1",
        task_type="ping",
        payload={"x": 1},
    )


def always_true(ctx: TaskContext) -> bool:
    return True


def always_false(ctx: TaskContext) -> bool:
    return False


def test_empty_chain_calls_handler():
    chain = ContextMiddlewareChain()
    assert chain.execute(make_ctx(), always_true) is True
    assert chain.execute(make_ctx(), always_false) is False


def test_middleware_called_in_order():
    order = []

    def mw1(ctx, nxt):
        order.append(1)
        return nxt(ctx)

    def mw2(ctx, nxt):
        order.append(2)
        return nxt(ctx)

    chain = ContextMiddlewareChain()
    chain.use(mw1).use(mw2)
    chain.execute(make_ctx(), always_true)
    assert order == [1, 2]


def test_middleware_can_short_circuit():
    called = []

    def blocker(ctx, nxt):
        return False  # never calls nxt

    def recorder(ctx, nxt):
        called.append(True)
        return nxt(ctx)

    chain = ContextMiddlewareChain()
    chain.use(blocker).use(recorder)
    result = chain.execute(make_ctx(), always_true)
    assert result is False
    assert called == []


def test_logging_middleware_calls_log_fn():
    logs = []
    chain = ContextMiddlewareChain()
    chain.use(logging_middleware(log_fn=logs.append))
    chain.execute(make_ctx(), always_true)
    assert len(logs) == 2
    assert "start" in logs[0]
    assert "done" in logs[1]


def test_tag_injector_middleware_merges_tags():
    captured = {}

    def capture(ctx):
        captured.update(ctx.tags)
        return True

    chain = ContextMiddlewareChain()
    chain.use(tag_injector_middleware({"env": "test", "version": "1"}))
    chain.execute(make_ctx(), capture)
    assert captured["env"] == "test"
    assert captured["version"] == "1"


def test_use_returns_chain_for_fluent_api():
    chain = ContextMiddlewareChain()
    result = chain.use(lambda ctx, nxt: nxt(ctx))
    assert result is chain
