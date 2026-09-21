from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProcessingStatus(StrEnum):
    SUCCESS = "SUCCESS"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class OCRPolicy(StrEnum):
    AUTO = "auto"
    ENABLE = "enable"
    DISABLE = "disable"


@dataclass
class ProcessingResult:
    status: ProcessingStatus
    engine: str
    ocr_used: bool
    content: Any | None = None
    error: Exception | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status is ProcessingStatus.SUCCESS
