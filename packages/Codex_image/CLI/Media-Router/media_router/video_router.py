from __future__ import annotations

import json
import hashlib
import re
import subprocess
import wave
from pathlib import Path

from .concurrency import SlotLease
from .errors import FailureClass, MediaRouterError
from .image_inputs import MAX_PROVIDER_IMAGE_LONG_EDGE, prepare_provider_images
from .schemas import MediaRequest, MediaResult, TaskContext
from .task_store import TaskStore


DEFAULT_VIDEO_MODEL = "seedance2.5"
DEFAULT_VIDEO_RESOLUTION = "480p"
TEST_VIDEO_MODEL = "seedance2.0"
TEST_VIDEO_RESOLUTION = "720p"
SUPPORTED_VIDEO_MODELS = {"seedance2.0", "seedance2.0mini", "seedance2.0fast_vip", "seedance2.0_vip", DEFAULT_VIDEO_MODEL}
PLACEHOLDER_PROMPTS = {"test", "测试", "motion", "正式版", "prompt"}


def audio_duration(path: Path) -> float:
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as stream:
            return stream.getnframes() / float(stream.getframerate())
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Cannot validate audio duration: {path}") from exc
    if completed.returncode:
        raise ValueError(f"Cannot validate audio duration: {path}")
    return float(json.loads(completed.stdout)["format"]["duration"])


def select_video_command(request: MediaRequest) -> str:
    if request.video_command:
        if request.video_command == "multiframe2video":
            raise ValueError("multiframe2video is a disabled legacy command; use multimodal2video")
        if request.video_command == "frames2video":
            raise ValueError(f"{request.video_command} is disabled; use multimodal2video")
        if request.video_command not in {"text2video", "image2video", "multimodal2video"}:
            raise ValueError(f"Unsupported video command: {request.video_command}")
        return request.video_command
    if request.audios and not request.images and not request.videos and request.video_model not in (None, DEFAULT_VIDEO_MODEL):
        raise ValueError(f"Audio-only multimodal input requires {DEFAULT_VIDEO_MODEL}")
    if request.videos or request.audios:
        return "multimodal2video"
    if not request.images:
        return "text2video"
    return "multimodal2video"


def _prompt_preferences(prompt: str) -> tuple[str | None, str | None, str | None]:
    ratio = next((value for value in ("21:9", "16:9", "9:16", "4:3", "3:4", "1:1") if value in prompt), None)
    # Prefer an explicitly labelled video duration.  Never interpret terminal
    # telemetry such as "Wall time: 0.6 seconds" as a generation duration.
    labelled = re.search(r"(?i)(?:视频时长|video\s*duration)\s*[:：]?\s*(\d{1,2})\s*(?:秒|s(?:ec(?:onds?)?)?)\b", prompt)
    duration_match = labelled or re.search(r"(?i)(?<![.\d])([4-9]|[12]\d|30)\s*(?:秒|s(?:ec(?:onds?)?)?)\b", prompt)
    duration = duration_match.group(1) if duration_match and 4 <= int(duration_match.group(1)) <= 30 else None
    return ratio, duration, None


def build_video_arguments(command: str, request: MediaRequest) -> list[str]:
    if command == "multiframe2video":
        raise ValueError("multiframe2video is a disabled legacy command; use multimodal2video")
    if command == "frames2video":
        raise ValueError(f"{command} is disabled; use multimodal2video")
    ratio, duration, resolution = _prompt_preferences(request.prompt)
    ratio = request.video_ratio or ratio
    duration = request.video_duration or duration
    resolution = request.video_resolution
    selected_model = request.video_model or DEFAULT_VIDEO_MODEL
    poll = "180"
    if request.video_execution_mode in {"test_submit_only", "production_submit_only", "production_batch"}:
        poll = "0"
    if request.video_execution_mode == "test_submit_only":
        selected_model = TEST_VIDEO_MODEL
        resolution = TEST_VIDEO_RESOLUTION
    args: list[str] = []
    if command == "text2video":
        args += ["--prompt", request.prompt]
    elif command == "image2video":
        args += ["--image", str(request.images[0]), "--prompt", request.prompt]
    elif command == "multimodal2video":
        for path in request.images:
            args += ["--image", str(path)]
        for path in request.videos:
            args += ["--video", str(path)]
        for path in request.audios:
            args += ["--audio", str(path)]
        args += ["--prompt", request.prompt]
    args += ["--model_version", selected_model, "--video_resolution", resolution or DEFAULT_VIDEO_RESOLUTION]
    if duration:
        args += ["--duration", duration]
    if ratio and command in ("text2video", "multimodal2video"):
        args += ["--ratio", ratio]
    if request.video_session_id:
        args += ["--session", request.video_session_id]
    args += ["--poll", poll]
    return args


class VideoRouter:
    def __init__(self, config: dict, provider, store: TaskStore | None = None, duration_probe=audio_duration):
        self.config, self.provider, self.store, self.duration_probe = config, provider, store or TaskStore(), duration_probe

    def validate(self, request: MediaRequest) -> str:
        prompt = request.prompt.strip()
        if not prompt:
            raise ValueError("prompt must not be empty")
        if request.video_execution_mode not in {"production", "production_submit_only", "production_batch", "test_submit_only"}:
            raise ValueError(f"Unsupported video_execution_mode: {request.video_execution_mode}")
        selected_model = TEST_VIDEO_MODEL if request.video_execution_mode == "test_submit_only" else request.video_model or DEFAULT_VIDEO_MODEL
        if request.video_execution_mode == "production_submit_only" and prompt.casefold() in PLACEHOLDER_PROMPTS:
            raise ValueError("Production video prompt is an obvious placeholder; submit the reviewed prompt text")
        if request.video_execution_mode == "production_submit_only":
            expected_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            if request.video_prompt_sha256 != expected_hash:
                raise ValueError("production_submit_only requires the SHA-256 of the exact reviewed prompt")
        if selected_model not in SUPPORTED_VIDEO_MODELS:
            raise ValueError(f"Unsupported video model: {selected_model}")
        if request.video_execution_mode != "test_submit_only" and selected_model != DEFAULT_VIDEO_MODEL and request.video_model_selection_source != "user_explicit":
            raise ValueError(
                "Seedance 2.0 models require video_model_selection_source=user_explicit; "
                "never infer or automatically fall back from Seedance 2.5 to 2.0"
            )
        _, inferred_duration, _ = _prompt_preferences(request.prompt)
        selected_duration = request.video_duration or inferred_duration
        selected_resolution = request.video_resolution or DEFAULT_VIDEO_RESOLUTION
        allowed_resolutions = {"480p", "720p", "1080p"} if selected_model == DEFAULT_VIDEO_MODEL else {"480p", "720p", "1080p", "4k"}
        if selected_resolution not in allowed_resolutions:
            raise ValueError(f"Resolution {selected_resolution} is unsupported for {selected_model}")
        if request.video_execution_mode != "test_submit_only":
            if not all((request.video_confirmation_model, request.video_confirmation_resolution, request.video_confirmation_duration)):
                raise ValueError("Formal video submission requires confirmation of model, resolution, and duration")
            if request.video_confirmation_model != selected_model:
                raise ValueError("Confirmed video model does not match the final request")
            if request.video_confirmation_resolution != selected_resolution:
                raise ValueError("Confirmed video resolution does not match the final request")
            if selected_duration is None or request.video_confirmation_duration != str(selected_duration):
                raise ValueError("Confirmed video duration does not match the final request")
        if request.video_execution_mode == "test_submit_only" and selected_duration and not 4 <= int(selected_duration) <= 15:
            raise ValueError("The seedance2.0 test channel supports 4-15 second output")
        command = select_video_command(request)
        if command == "multimodal2video":
            if selected_model != DEFAULT_VIDEO_MODEL and request.audios and not request.images and not request.videos:
                raise ValueError(f"Audio-only multimodal input requires {DEFAULT_VIDEO_MODEL}")
            image_limit = 30 if selected_model == "seedance2.5" else 9
            limits = ((request.images, image_limit, "images"), (request.videos, 10 if selected_model == "seedance2.5" else 3, "videos"), (request.audios, 10 if selected_model == "seedance2.5" else 3, "audios"))
            max_total = 50 if selected_model == "seedance2.5" else 12
            if sum(len(values) for values, _, _ in limits) > max_total:
                raise ValueError(f"At most {max_total} total inputs are allowed for {selected_model} multimodal2video")
        else:
            limits = ((request.images, 1, "images"), (request.videos, 0, "videos"), (request.audios, 0, "audios"))
        for values, limit, label in limits:
            if len(values) > limit:
                raise ValueError(f"At most {limit} {label} are allowed")
            missing = [str(path) for path in values if not path.is_file()]
            if missing:
                raise FileNotFoundError("Missing local media: " + "; ".join(missing))
        audio_max_duration = 30 if selected_model == DEFAULT_VIDEO_MODEL else 15
        for path in request.audios:
            duration = self.duration_probe(path)
            if not 2 <= duration <= audio_max_duration:
                raise ValueError(f"Audio duration must be 2-{audio_max_duration} seconds: {path}")
        return command

    def execute(self, request: MediaRequest, context: TaskContext | None = None) -> MediaResult:
        try:
            command = self.validate(request)
        except (ValueError, FileNotFoundError) as exc:
            return MediaResult(context.task_id if context else "uncreated", "failed", failure_class=FailureClass.INPUT_ERROR.value, safe_reason=str(exc))
        context = context or self.store.create(request)
        self.store.set_state(context, "running", command=command)
        try:
            provider_request = prepare_provider_images(
                request,
                context,
                int(self.config.get("media_inputs", {}).get("max_image_long_edge", MAX_PROVIDER_IMAGE_LONG_EDGE)),
            )
        except (ValueError, TimeoutError) as exc:
            final = MediaResult(context.task_id, "failed", failure_class=FailureClass.INPUT_ERROR.value, safe_reason=str(exc))
            self.store.set_state(context, final.status, failure_class=final.failure_class)
            self.store.write_result(context, final.to_dict())
            return final
        readiness = self.provider.check_readiness()
        if not readiness.ready:
            final = MediaResult(context.task_id, "failed", failure_class=FailureClass.AUTH_UNAVAILABLE.value, safe_reason=readiness.reason)
        else:
            capacity_key = "dreamina-video-test" if request.video_execution_mode == "test_submit_only" else self.provider.capacity_key
            slots = 1 if request.video_execution_mode == "test_submit_only" else self.provider.max_concurrency
            wait_timeout = 0.1 if request.video_execution_mode == "test_submit_only" else 180.0
            lease = SlotLease(self.store.private_root / "locks" / "providers", capacity_key, context.task_id, slots=slots, wait_timeout=wait_timeout, cancel_path=context.cancelled_file)
            try:
                with lease:
                    result = self.provider.execute_command(command, build_video_arguments(command, provider_request), provider_request, context)
            except MediaRouterError as exc:
                status = "cancelled" if exc.failure_class == FailureClass.CANCELLED else "needs_review" if exc.failure_class == FailureClass.INDETERMINATE_SUBMISSION else "failed"
                final = MediaResult(context.task_id, status, failure_class=exc.failure_class.value, safe_reason=str(exc))
            except Exception as exc:
                final = MediaResult(context.task_id, "needs_review", failure_class=FailureClass.INDETERMINATE_SUBMISSION.value, safe_reason=f"Adapter raised {type(exc).__name__}")
            else:
                attempt = result.to_dict()
                if result.status == "success":
                    final = MediaResult(context.task_id, "success", result.output_path, result.provider_id, result.model_id, [attempt], submit_id=result.submit_id)
                elif result.status == "submitted":
                    final = MediaResult(
                        context.task_id,
                        "submitted",
                        provider_id=result.provider_id,
                        model_id=result.model_id,
                        attempts=[attempt],
                        submit_id=result.submit_id,
                        next_action=("check_dreamina_web" if request.video_execution_mode == "test_submit_only" else "query_later"),
                        user_message=(
                            "测试任务已发送，请到即梦网站后台查看结果。"
                            if request.video_execution_mode == "test_submit_only"
                            else "视频任务已发送。"
                        ),
                    )
                else:
                    failure = result.failure_class or FailureClass.INDETERMINATE_SUBMISSION
                    final = MediaResult(context.task_id, result.status, attempts=[attempt], failure_class=failure.value, safe_reason=result.safe_reason)
        if final.status == "submitted":
            attempt = final.attempts[-1] if final.attempts else {}
            self.store.set_state(
                context,
                final.status,
                submit_id=final.submit_id,
                model_id=final.model_id,
                provider_status=attempt.get("provider_status"),
                polling_performed=False,
            )
        else:
            self.store.set_state(context, final.status, failure_class=final.failure_class)
        self.store.write_result(context, final.to_dict())
        return final
