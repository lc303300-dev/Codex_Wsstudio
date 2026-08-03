from __future__ import annotations

from typing import Literal, Protocol

from ..schemas import MediaRequest, ProviderResult, Readiness, TaskContext


class MediaProvider(Protocol):
    provider_id: str
    model_id: str
    capability: Literal["image", "video"]
    capacity_key: str
    max_concurrency: int

    def check_readiness(self) -> Readiness: ...
    def execute(self, request: MediaRequest, context: TaskContext) -> ProviderResult: ...
