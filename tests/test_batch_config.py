import pytest
from retryq.batch_config import BatchConfig


def test_defaults():
    cfg = BatchConfig()
    assert cfg.batch_size == 10
    assert cfg.batch_timeout == 5.0
    assert cfg.max_retries == 5
    assert cfg.enable_metrics is False


def test_custom_values():
    cfg = BatchConfig(batch_size=20, batch_timeout=2.5, max_retries=3, enable_metrics=True)
    assert cfg.batch_size == 20
    assert cfg.batch_timeout == 2.5
    assert cfg.max_retries == 3
    assert cfg.enable_metrics is True


def test_invalid_batch_size_raises():
    with pytest.raises(ValueError, match="batch_size"):
        BatchConfig(batch_size=0)


def test_negative_batch_size_raises():
    with pytest.raises(ValueError, match="batch_size"):
        BatchConfig(batch_size=-5)


def test_invalid_batch_timeout_raises():
    with pytest.raises(ValueError, match="batch_timeout"):
        BatchConfig(batch_timeout=0)


def test_negative_batch_timeout_raises():
    with pytest.raises(ValueError, match="batch_timeout"):
        BatchConfig(batch_timeout=-1.0)


def test_invalid_max_retries_raises():
    with pytest.raises(ValueError, match="max_retries"):
        BatchConfig(max_retries=-1)


def test_from_dict_full():
    data = {"batch_size": 5, "batch_timeout": 3.0, "max_retries": 2, "enable_metrics": True}
    cfg = BatchConfig.from_dict(data)
    assert cfg.batch_size == 5
    assert cfg.batch_timeout == 3.0
    assert cfg.max_retries == 2
    assert cfg.enable_metrics is True


def test_from_dict_ignores_unknown_keys():
    data = {"batch_size": 4, "unknown_key": "ignored"}
    cfg = BatchConfig.from_dict(data)
    assert cfg.batch_size == 4
    assert cfg.batch_timeout == 5.0  # default


def test_to_dict_roundtrip():
    cfg = BatchConfig(batch_size=7, batch_timeout=1.5, max_retries=4, enable_metrics=True)
    d = cfg.to_dict()
    assert d == {
        "batch_size": 7,
        "batch_timeout": 1.5,
        "max_retries": 4,
        "enable_metrics": True,
    }
    restored = BatchConfig.from_dict(d)
    assert restored == cfg
