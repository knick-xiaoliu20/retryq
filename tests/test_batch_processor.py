import pytest
from unittest.mock import MagicMock, patch, call
from retryq.batch_processor import BatchProcessor


@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.dequeue.return_value = None
    return q


@pytest.fixture
def handler():
    return MagicMock(return_value=True)


@pytest.fixture
def processor(mock_queue, handler):
    return BatchProcessor(queue=mock_queue, handler=handler, batch_size=3, batch_timeout=1.0)


def test_invalid_batch_size_raises(mock_queue, handler):
    with pytest.raises(ValueError, match="batch_size"):
        BatchProcessor(queue=mock_queue, handler=handler, batch_size=0)


def test_invalid_batch_timeout_raises(mock_queue, handler):
    with pytest.raises(ValueError, match="batch_timeout"):
        BatchProcessor(queue=mock_queue, handler=handler, batch_timeout=-1.0)


def test_collect_batch_empty_queue(processor, mock_queue):
    mock_queue.dequeue.return_value = None
    tasks = processor.collect_batch()
    assert tasks == []


def test_collect_batch_up_to_batch_size(processor, mock_queue):
    task = {"id": "t1", "payload": {}}
    mock_queue.dequeue.side_effect = [task, task, task, task]
    tasks = processor.collect_batch()
    assert len(tasks) == 3  # capped at batch_size


def test_process_batch_all_succeed(processor, mock_queue, handler):
    task = {"id": "t1", "payload": {}}
    mock_queue.dequeue.side_effect = [task, task, None]
    handler.return_value = True

    result = processor.process_batch()

    assert result["succeeded"] == 2
    assert result["failed"] == 0
    assert result["processed"] == 2
    assert mock_queue.acknowledge.call_count == 2


def test_process_batch_handler_failure_requeues(processor, mock_queue, handler):
    task = {"id": "t2", "payload": {}}
    mock_queue.dequeue.side_effect = [task, None]
    handler.return_value = False

    result = processor.process_batch()

    assert result["failed"] == 1
    assert result["succeeded"] == 0
    mock_queue.requeue.assert_called_once_with(task)


def test_process_batch_handler_exception_requeues(processor, mock_queue, handler):
    task = {"id": "t3", "payload": {}}
    mock_queue.dequeue.side_effect = [task, None]
    handler.side_effect = RuntimeError("boom")

    result = processor.process_batch()

    assert result["failed"] == 1
    mock_queue.requeue.assert_called_once_with(task)


def test_process_batch_records_metrics(mock_queue, handler):
    metrics = MagicMock()
    processor = BatchProcessor(
        queue=mock_queue, handler=handler, batch_size=2, batch_timeout=1.0, metrics=metrics
    )
    task = {"id": "t4", "payload": {}}
    mock_queue.dequeue.side_effect = [task, None]
    handler.return_value = True

    processor.process_batch()

    metrics.record_dequeue.assert_called_once()
    metrics.record_success.assert_called_once()


def test_run_stops_after_max_batches(mock_queue, handler):
    processor = BatchProcessor(queue=mock_queue, handler=handler, batch_size=2, batch_timeout=0.1)
    mock_queue.dequeue.return_value = None
    processor.run(max_batches=3)
    # Should complete without hanging
    assert not processor._running


def test_stop_sets_running_false(processor):
    processor._running = True
    processor.stop()
    assert not processor._running
