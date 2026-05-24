"""Tests for retryq.task_router.TaskRouter."""

import pytest
from retryq.task_router import TaskRouter, RouteNotFoundError


@pytest.fixture
def router():
    return TaskRouter()


def test_register_and_dispatch(router):
    results = []
    router.register("ping", lambda task: results.append(task["type"]))
    router.dispatch({"type": "ping"})
    assert results == ["ping"]


def test_route_decorator(router):
    called_with = {}

    @router.route("send_email")
    def handle_email(task):
        called_with.update(task)

    router.dispatch({"type": "send_email", "to": "a@b.com"})
    assert called_with["to"] == "a@b.com"


def test_dispatch_unknown_type_raises(router):
    with pytest.raises(RouteNotFoundError, match="unknown_type"):
        router.dispatch({"type": "unknown_type"})


def test_dispatch_none_type_raises(router):
    with pytest.raises(RouteNotFoundError):
        router.dispatch({"type": None})


def test_default_handler_used_as_fallback():
    fallback_calls = []
    router = TaskRouter(default_handler=lambda t: fallback_calls.append(t["type"]))
    router.dispatch({"type": "anything"})
    assert fallback_calls == ["anything"]


def test_registered_handler_takes_priority_over_default():
    results = []
    router = TaskRouter(default_handler=lambda t: results.append("default"))
    router.register("ping", lambda t: results.append("specific"))
    router.dispatch({"type": "ping"})
    assert results == ["specific"]


def test_registered_types(router):
    router.register("a", lambda t: None)
    router.register("b", lambda t: None)
    assert set(router.registered_types()) == {"a", "b"}


def test_has_route_true(router):
    router.register("job", lambda t: None)
    assert router.has_route("job") is True


def test_has_route_false(router):
    assert router.has_route("missing") is False


def test_register_non_callable_raises(router):
    with pytest.raises(TypeError, match="callable"):
        router.register("bad", "not_a_function")


def test_route_decorator_empty_type_raises(router):
    with pytest.raises(ValueError, match="non-empty string"):
        router.route("")


def test_register_empty_type_raises(router):
    with pytest.raises(ValueError, match="non-empty string"):
        router.register("", lambda t: None)


def test_handler_return_value_propagated(router):
    router.register("compute", lambda t: 42)
    result = router.dispatch({"type": "compute"})
    assert result == 42
