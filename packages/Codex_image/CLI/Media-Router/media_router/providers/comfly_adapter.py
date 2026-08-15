from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic

from ..errors import FailureClass, MediaRouterError
from ..config import PRIVATE_ROOT
from ..provider_runtime import ProviderRuntime
from ..schemas import MediaRequest, ProviderResult, Readiness, TaskContext
from . import comfly_common


class ComflyAdapter:
    capability = "image"

    def __init__(self, provider_id: str, model_id: str, max_concurrency: int = 6):
        self.provider_id = provider_id
        self.model_id = model_id
        self.capacity_key = provider_id
        self.max_concurrency = max_concurrency
        self.runtime = ProviderRuntime(PRIVATE_ROOT / "logs" / "providers", provider_id)

    def check_readiness(self) -> Readiness:
        available, reason = self.runtime.readiness()
        if not available:
            return Readiness(False, reason)
        return Readiness(bool(comfly_common.api_key()), None if comfly_common.api_key() else "COMFLY_API_KEY is not configured")

    def execute(self, request: MediaRequest, context: TaskContext) -> ProviderResult:
        started, stamp = monotonic(), datetime.now(timezone.utc).isoformat()
        output = context.output_dir / f"{self.provider_id}.png"
        try:
            details = comfly_common.execute_once(
                self.model_id,
                request.prompt,
                request.images,
                output,
                size=request.image_ratio,
                deadline=context.provider_deadline,
                timeout_failure=FailureClass.PROVIDER_TIMEOUT if context.provider_deadline is not None else None,
            )
            duration = int((monotonic()-started)*1000)
            self.runtime.record(True, duration)
            return ProviderResult(self.provider_id, self.model_id, "success", request_id=details["request_id"], output_path=str(output), output_bytes=details["output_bytes"], started_at=stamp, finished_at=datetime.now(timezone.utc).isoformat(), duration_ms=duration)
        except MediaRouterError as exc:
            duration = int((monotonic()-started)*1000)
            self.runtime.record(False, duration)
            status = "needs_review" if exc.failure_class.value == "indeterminate_submission" else "cancelled" if exc.failure_class.value == "cancelled" else "failed"
            return ProviderResult(self.provider_id, self.model_id, status, failure_class=exc.failure_class, safe_reason=str(exc), started_at=stamp, finished_at=datetime.now(timezone.utc).isoformat(), duration_ms=duration)
