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
    video_command: str | None = None
    video_model: str | None = None
    video_model_selection_source: str | None = None
    video_execution_mode: str = "production"  # production_submit_only is reserved for trusted local pipelines
    video_ratio: str | None = None
    video_duration: str | None = None
    video_resolution: str | None = None
    image_provider: str | None = None
    image_model: str | None = None
    image_ratio: str | None = None
    image_resolution: str | None = None


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
    status: Literal["success", "submitted", "failed", "needs_review", "cancelled"]
    failure_class: FailureClass | None = None
    request_id: str | None = None
    submit_id: str | None = None
    output_path: str | None = None
    output_bytes: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int = 0
    safe_reason: str | None = None
    provider_status: str | None = None
    polling_performed: bool | None = None

    def to_dict(self) -> dict:
        value = asdict(self)
        if self.failure_class is not None:
            value["failure_class"] = self.failure_class.value
        return value


@dataclass
class MediaResult:
    task_id: str
    status: Literal["success", "submitted", "failed", "needs_review", "cancelled"]
    output_path: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    attempts: list[dict] = field(default_factory=list)
    failure_class: str | None = None
    safe_reason: str | None = None
    submit_id: str | None = None
    next_action: str | None = None
    user_message: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
