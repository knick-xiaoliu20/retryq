from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BatchConfig:
    """
    Configuration dataclass for BatchProcessor.

    Attributes:
        batch_size: Maximum number of tasks to process per batch.
        batch_timeout: Maximum seconds to wait while collecting a batch.
        max_retries: Maximum number of times a task may be requeued before
                     it is considered permanently failed.
        enable_metrics: Whether to attach a MetricsCollector to the processor.
    """

    batch_size: int = 10
    batch_timeout: float = 5.0
    max_retries: int = 5
    enable_metrics: bool = False

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")
        if self.batch_timeout <= 0:
            raise ValueError(f"batch_timeout must be > 0, got {self.batch_timeout}")
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")

    @classmethod
    def from_dict(cls, data: dict) -> "BatchConfig":
        """Construct a BatchConfig from a plain dictionary."""
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in allowed}
        return cls(**filtered)

    def to_dict(self) -> dict:
        """Serialise the config to a plain dictionary."""
        return {
            "batch_size": self.batch_size,
            "batch_timeout": self.batch_timeout,
            "max_retries": self.max_retries,
            "enable_metrics": self.enable_metrics,
        }
