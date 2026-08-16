from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from .concurrency import SlotLease
from .errors import FALLBACK_FAILURES, FailureClass, MediaRouterError
from .image_inputs import MAX_PROVIDER_IMAGE_LONG_EDGE, prepare_provider_images
from .output_validation import is_valid_image
from .schemas import MediaRequest, MediaResult, TaskContext
from .task_store import TaskStore

SUPPORTED_IMAGE_RATIOS = {"21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"}
SUPPORTED_IMAGE_RESOLUTIONS = {"1K", "2K", "4K"}


class ImageRouter:
    def __init__(self, config: dict, registry: dict, store: TaskStore | None = None):
        self.config, self.registry = config, registry
        self.store = store or TaskStore()

    def ordered_providers(self, request: MediaRequest) -> list:
        configured = self.config["providers"]
        requested = request.image_provider
        image_ids = [provider_id for provider_id, provider in self.registry.items() if provider.capability == "image" and configured[provider_id].get("enabled", True)]
        if requested:
            image_ids = [item for item in image_ids if item == requested]
        return [self.registry[provider_id] for provider_id in sorted(image_ids, key=lambda item: configured[item]["priority"])]

    def validate(self, request: MediaRequest) -> None:
        if not request.prompt.strip():
            raise ValueError("prompt must not be empty")
        if request.videos or request.audios:
            raise ValueError("generate_image accepts only prompt and images")
        if not request.image_ratio:
            raise ValueError("image_ratio is required; ask the user to choose an image ratio before generation")
        if request.image_ratio not in SUPPORTED_IMAGE_RATIOS:
            raise ValueError("Unsupported image_ratio: " + request.image_ratio)
        if request.image_resolution is not None and request.image_resolution not in SUPPORTED_IMAGE_RESOLUTIONS:
            raise ValueError("Unsupported image_resolution: " + request.image_resolution)
        if request.image_provider:
            provider = self.registry.get(request.image_provider)
            configured = self.config.get("providers", {}).get(request.image_provider)
            if provider is None or configured is None or provider.capability != "image":
                raise ValueError("Unsupported image_provider: " + request.image_provider)
            if not configured.get("enabled", True):
                raise ValueError("Requested image_provider is disabled: " + request.image_provider)
        missing = [str(path) for path in request.images if not path.is_file()]
        if missing:
            raise FileNotFoundError("Missing reference images: " + "; ".join(missing))

    def execute(self, request: MediaRequest, context: TaskContext | None = None) -> MediaResult:
        try:
            self.validate(request)
        except (ValueError, FileNotFoundError) as exc:
            return MediaResult(context.task_id if context else "uncreated", "failed", failure_class=FailureClass.INPUT_ERROR.value, safe_reason=str(exc))
        timeout_config = self.config.get("image_timeouts", {})
        provider_seconds = float(timeout_config.get("provider_seconds", 120))
        task_seconds = float(timeout_config.get("task_seconds", 300))
        task_deadline = time.monotonic() + task_seconds
        context = context or self.store.create(request)
        self.store.set_state(context, "running")
        attempts: list[dict] = []

        def task_timeout() -> MediaResult:
            final = MediaResult(
                context.task_id,
                "failed",
                attempts=attempts,
                failure_class=FailureClass.TASK_TIMEOUT.value,
                safe_reason=f"Image task exceeded {task_seconds:g} seconds",
            )
            self.store.set_state(context, "failed", failure_class=final.failure_class)
            self.store.write_result(context, final.to_dict())
            return final

        try:
            provider_request = prepare_provider_images(
                request,
                context,
                int(self.config.get("media_inputs", {}).get("max_image_long_edge", MAX_PROVIDER_IMAGE_LONG_EDGE)),
                task_deadline,
            )
        except (ValueError, TimeoutError) as exc:
            failure = FailureClass.TASK_TIMEOUT if isinstance(exc, TimeoutError) else FailureClass.INPUT_ERROR
            final = MediaResult(context.task_id, "failed", failure_class=failure.value, safe_reason=str(exc))
            self.store.set_state(context, "failed", failure_class=final.failure_class)
            self.store.write_result(context, final.to_dict())
            return final

        for provider in self.ordered_providers(request):
            if time.monotonic() >= task_deadline:
                return task_timeout()
            readiness = provider.check_readiness()
            if time.monotonic() >= task_deadline:
                return task_timeout()
            if not readiness.ready:
                attempt = {
                    "provider_id": provider.provider_id,
                    "model_id": provider.model_id,
                    "status": "failed",
                    "failure_class": FailureClass.AUTH_UNAVAILABLE.value,
                    "safe_reason": readiness.reason or "Provider is unavailable",
                }
                attempts.append(attempt)
                continue
            provider_deadline = min(time.monotonic() + provider_seconds, task_deadline)
            lease = SlotLease(
                self.store.private_root / "locks" / "providers",
                provider.capacity_key,
                context.task_id,
                slots=provider.max_concurrency,
                wait_timeout=max(0.001, provider_deadline - time.monotonic()),
                cancel_path=context.cancelled_file,
            )
            try:
                with lease:
                    execution_context = replace(context, provider_deadline=provider_deadline, task_deadline=task_deadline)
                    result = provider.execute(provider_request, execution_context)
            except MediaRouterError as exc:
                result = None
                failure_class = exc.failure_class
                if failure_class == FailureClass.TIMEOUT_BEFORE_SUBMIT and time.monotonic() >= provider_deadline:
                    failure_class = FailureClass.PROVIDER_TIMEOUT
                attempt = {
                    "provider_id": provider.provider_id,
                    "model_id": provider.model_id,
                    "status": "cancelled" if failure_class == FailureClass.CANCELLED else "needs_review" if failure_class == FailureClass.INDETERMINATE_SUBMISSION else "failed",
                    "failure_class": failure_class.value,
                    "safe_reason": str(exc),
                }
            except Exception as exc:
                result = None
                attempt = {
                    "provider_id": provider.provider_id,
                    "model_id": provider.model_id,
                    "status": "needs_review",
                    "failure_class": FailureClass.INDETERMINATE_SUBMISSION.value,
                    "safe_reason": f"Adapter raised {type(exc).__name__}",
                }
            else:
                attempt = result.to_dict()
            if time.monotonic() >= task_deadline:
                if attempt.get("failure_class") != FailureClass.TASK_TIMEOUT.value:
                    attempts.append(attempt)
                return task_timeout()
            if time.monotonic() >= provider_deadline:
                result = None
                attempt.update({
                    "status": "failed",
                    "failure_class": FailureClass.PROVIDER_TIMEOUT.value,
                    "safe_reason": f"Image provider exceeded {provider_seconds:g} seconds",
                })
            attempts.append(attempt)
            if result and result.status == "success" and result.output_path and is_valid_image(Path(result.output_path)):
                final = MediaResult(context.task_id, "success", result.output_path, result.provider_id, result.model_id, attempts)
                self.store.set_state(context, "success")
                self.store.write_result(context, final.to_dict())
                return final
            failure = FailureClass(attempt.get("failure_class", FailureClass.DEFINITE_PROVIDER_FAILURE.value))
            if failure not in FALLBACK_FAILURES:
                status = "needs_review" if failure == FailureClass.INDETERMINATE_SUBMISSION else "cancelled" if failure == FailureClass.CANCELLED else "failed"
                final = MediaResult(context.task_id, status, attempts=attempts, failure_class=failure.value, safe_reason=attempt.get("safe_reason"))
                self.store.set_state(context, status, failure_class=failure.value)
                self.store.write_result(context, final.to_dict())
                return final
        final = MediaResult(context.task_id, "failed", attempts=attempts, failure_class=FailureClass.DEFINITE_PROVIDER_FAILURE.value, safe_reason="All configured image adapters failed")
        self.store.set_state(context, "failed", failure_class=final.failure_class)
        self.store.write_result(context, final.to_dict())
        return final
