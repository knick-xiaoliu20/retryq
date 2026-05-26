import pytest
from retryq.task_filter import TaskFilter, FilterRejectedError


@pytest.fixture
def task():
    return {
        "type": "email",
        "attempts": 0,
        "payload": {"to": "user@example.com", "subject": "Hi"},
    }


def test_empty_filter_allows_any_task(task):
    tf = TaskFilter()
    assert tf.evaluate(task) is True


def test_allow_types_passes_matching_type(task):
    tf = TaskFilter().allow_types("email", "sms")
    assert tf.evaluate(task) is True


def test_allow_types_rejects_unknown_type(task):
    task["type"] = "webhook"
    tf = TaskFilter().allow_types("email", "sms")
    with pytest.raises(FilterRejectedError, match="webhook"):
        tf.evaluate(task)


def test_allow_types_supports_glob(task):
    task["type"] = "email.transactional"
    tf = TaskFilter().allow_types("email.*")
    assert tf.evaluate(task) is True


def test_require_fields_passes_when_present(task):
    tf = TaskFilter().require_fields("to", "subject")
    assert tf.evaluate(task) is True


def test_require_fields_rejects_when_missing(task):
    tf = TaskFilter().require_fields("to", "body")
    with pytest.raises(FilterRejectedError, match="body"):
        tf.evaluate(task)


def test_max_attempts_allows_under_limit(task):
    task["attempts"] = 2
    tf = TaskFilter().max_attempts(5)
    assert tf.evaluate(task) is True


def test_max_attempts_rejects_at_limit(task):
    task["attempts"] = 5
    tf = TaskFilter().max_attempts(5)
    with pytest.raises(FilterRejectedError, match="5 >= 5"):
        tf.evaluate(task)


def test_max_attempts_rejects_over_limit(task):
    task["attempts"] = 10
    tf = TaskFilter().max_attempts(3)
    with pytest.raises(FilterRejectedError):
        tf.evaluate(task)


def test_chained_filters_all_must_pass(task):
    tf = (
        TaskFilter()
        .allow_types("email")
        .require_fields("to", "subject")
        .max_attempts(3)
    )
    assert tf.evaluate(task) is True


def test_chained_filters_first_failure_raises(task):
    task["type"] = "unknown"
    tf = (
        TaskFilter()
        .allow_types("email")
        .require_fields("to")
    )
    with pytest.raises(FilterRejectedError, match="unknown"):
        tf.evaluate(task)


def test_custom_filter_can_be_added(task):
    def reject_large_payload(t):
        if len(str(t.get("payload", ""))) > 1000:
            raise FilterRejectedError("payload too large")
        return True

    tf = TaskFilter().add(reject_large_payload)
    assert tf.evaluate(task) is True


def test_add_returns_self_for_chaining():
    tf = TaskFilter()
    result = tf.add(lambda t: True)
    assert result is tf
