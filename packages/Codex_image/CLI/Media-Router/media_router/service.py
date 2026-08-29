from __future__ import annotations

from pathlib import Path
import re
from dataclasses import replace
from datetime import date


def validate_prompt_completeness(prompt: str) -> None:
    """Reject only universally invalid prompt payloads at the shared boundary."""
    text = (prompt or "").strip()
    if not text:
        raise ValueError("Prompt is empty")
    if re.search(
        r"(?im)^\s*(?:Exit code|Wall time|Output|Script completed|Script error)\s*:",
        text,
    ):
        raise ValueError("Prompt contains terminal execution metadata")


def normalize_video_duration(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("video_duration must be an integer number of seconds")
    text = str(value).strip()
    match = re.fullmatch(r"(\d{1,2})\s*(?:s(?:ec(?:onds?)?)?|秒)?", text, re.IGNORECASE)
    if not match:
        raise ValueError("video_duration must be an integer number of seconds, optionally followed by s or 秒")
    duration = int(match.group(1))
    if not 4 <= duration <= 30:
        raise ValueError("video_duration must be between 4 and 30 seconds")
    return str(duration)

from .config import load_config
from .image_router import ImageRouter
from .providers.registry import build_registry
from .scheduler import rolling_map
from .schemas import MediaRequest
from .video_router import VideoRouter


def dated_video_group(name: str, today: date | None = None) -> str:
    base = name.strip()
    if not base or len(base) > 20 or any(character in base for character in "\r\n"):
        raise ValueError("video_group base name must contain 1-20 characters on one line")
    return f"{(today or date.today()):%Y_%m_%d}-{base}"


def execute(command: str, prompt: str, images=(), videos=(), audios=(), **video_options) -> dict:
    # Fail closed at the provider boundary. Never try to repair or strip a
    # shell/tool wrapper: doing so could turn a polluted, truncated payload
    # into something that looks valid enough to consume credits.
    validate_prompt_completeness(prompt)
    config = load_config()
    registry = build_registry(config)
    normalized_duration = normalize_video_duration(video_options.get("video_duration"))
    normalized_confirmation_duration = normalize_video_duration(video_options.get("video_confirmation_duration"))
    request = MediaRequest(
        prompt.strip(),
        tuple(Path(path).resolve() for path in images),
        tuple(Path(path).resolve() for path in videos),
        tuple(Path(path).resolve() for path in audios),
        video_command=video_options.get("video_command"),
        video_model=video_options.get("video_model"),
        video_model_selection_source=video_options.get("video_model_selection_source"),
        video_execution_mode=video_options.get("video_execution_mode", "production"),
        video_ratio=video_options.get("video_ratio"),
        video_duration=normalized_duration,
        video_resolution=video_options.get("video_resolution"),
        video_session_id=None,
        video_confirmation_model=video_options.get("video_confirmation_model"),
        video_confirmation_resolution=video_options.get("video_confirmation_resolution"),
        video_confirmation_duration=normalized_confirmation_duration,
        video_prompt_sha256=video_options.get("video_prompt_sha256"),
        video_test_confirmation=video_options.get("video_test_confirmation"),
        image_provider=video_options.get("image_provider"),
        image_model=video_options.get("image_model"),
        image_ratio=video_options.get("image_ratio"),
        image_resolution=video_options.get("image_resolution"),
    )
    if command == "generate_image":
        return ImageRouter(config, registry).execute(request).to_dict()
    if command == "generate_video":
        count = int(video_options.get("video_count") or 1)
        if not 1 <= count <= 10:
            raise ValueError("video_count must be between 1 and 10")
        if request.video_execution_mode == "test_submit_only" and count != 1:
            raise ValueError("test_submit_only supports exactly one task")
        router = VideoRouter(config, registry["dreamina-video"])
        group = video_options.get("video_group")
        if request.video_execution_mode == "test_submit_only" and group is None:
            raise ValueError("test_submit_only requires video_group to verify session routing")
        resolved_group_name = None
        if group is not None:
            resolved_group_name = dated_video_group(str(group))
            request = replace(request, video_session_id=router.provider.resolve_session(resolved_group_name))
        if count == 1:
            result = router.execute(request).to_dict()
            if resolved_group_name:
                result.update({"video_group": resolved_group_name, "video_session_id": request.video_session_id})
            return result
        # Use a bounded rolling queue: keep at most six router submissions in
        # flight, and replenish a slot as soon as one returns submit_id.  The
        # router's production_batch mode is submit-only, so this never waits
        # for rendering while the queue is being filled. The DT batch entry
        # performs the single polling/download phase after this returns.
        batch_request = replace(request, video_execution_mode="production_batch")
        results = [item.to_dict() for item in rolling_map(
            (batch_request,) * count,
            router.execute,
            runtime_slots=router.provider.max_concurrency,
            configured_limit=6,
        )]
        statuses = {item.get("status") for item in results}
        aggregate_status = next(iter(statuses)) if len(statuses) == 1 and statuses <= {"success", "submitted"} else "partial"
        result = {
            "status": aggregate_status,
            "count": count,
            "results": results,
        }
        if resolved_group_name:
            result.update({"video_group": resolved_group_name, "video_session_id": request.video_session_id})
        return result
    raise ValueError("Unknown media command")
