from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .errors import FailureClass


@dataclass(frozen=True)
class MediaRequest:
    prompt: str
    images: tuple[Path, ...] = ()
    videos: tuple[Path, ...] = ()
    audios: tuple[Path, ...] = ()


@dataclass(frozen=True)
class TaskContext:
    batch_id: str
    task_id: str
    job_dir: Path
    output_dir: Path
    prompt_file: Path
    cancelled_file: Path
    provider_deadline: float | None = None
    task_deadline: float | None = None


@dataclass
class Readiness:
    ready: bool
    reason: str | None = None


@dataclass
class ProviderResult:
    provider_id: str
    model_id: str
    status: Literal["success", "failed", "needs_review", "cancelled"]
    failure_class: FailureClass | None = None
    request_id: str | None = None
    submit_id: str | None = None
    output_path: str | None = None
    output_bytes: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int = 0
    safe_reason: str | None = None

    def to_dict(self) -> dict:
        value = asdict(self)
        if self.failure_class is not None:
            value["failure_class"] = self.failure_class.value
        return value


@dataclass
class MediaResult:
    task_id: str
    status: Literal["success", "failed", "needs_review", "cancelled"]
    output_path: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    attempts: list[dict] = field(default_factory=list)
    failure_class: str | None = None
    safe_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
