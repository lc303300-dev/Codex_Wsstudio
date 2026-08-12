from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

from .concurrency import SlotLease
from .errors import FailureClass, MediaRouterError
from .image_inputs import MAX_PROVIDER_IMAGE_LONG_EDGE, prepare_provider_images
from .schemas import MediaRequest, MediaResult, TaskContext
from .task_store import TaskStore


FIRST_LAST_PATTERN = re.compile(r"(?i)(首尾帧|首帧.{0,8}尾帧|first.{0,8}last\s+frame|start.{0,8}end\s+frame)")
DEFAULT_VIDEO_MODEL = "seedance2.5"
DEFAULT_VIDEO_RESOLUTION = "480p"
MULTIMODAL_IMAGE_ORDER_PREFIX = (
    "参考引用规则：所有参考内容严格按命令行参数出现顺序绑定；图片1=第1个 --image，"
    "图片2=第2个 --image，视频1=第1个 --video，音频1=第1个 --audio。"
    "提示词必须使用这些裸标签，不得使用 @图片1、@Image 1，也不得按文件名、自然语言顺序或视觉猜测重新排序。\n"
)


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
        if request.video_command not in {"text2video", "image2video", "frames2video", "multiframe2video", "multimodal2video"}:
            raise ValueError(f"Unsupported video command: {request.video_command}")
        return request.video_command
    if request.audios and not request.images and not request.videos and request.video_model not in (None, DEFAULT_VIDEO_MODEL):
        raise ValueError(f"Audio-only multimodal input requires {DEFAULT_VIDEO_MODEL}")
    if request.videos or request.audios:
        return "multimodal2video"
    if not request.images:
        return "text2video"
    if len(request.images) == 2 and FIRST_LAST_PATTERN.search(request.prompt):
        return "frames2video"
    return "multimodal2video"


def _prompt_preferences(prompt: str) -> tuple[str | None, str | None, str | None]:
    ratio = next((value for value in ("21:9", "16:9", "9:16", "4:3", "3:4", "1:1") if value in prompt), None)
    duration_match = re.search(r"(?i)(\d{1,2})\s*(?:秒|s(?:ec(?:onds?)?)?)", prompt)
    duration = duration_match.group(1) if duration_match and 4 <= int(duration_match.group(1)) <= 30 else None
    resolution = next((value for value in ("4k", "1080p", "720p", "480p") if value.lower() in prompt.lower()), None)
    return ratio, duration, resolution


def build_video_arguments(command: str, request: MediaRequest) -> list[str]:
    ratio, duration, resolution = _prompt_preferences(request.prompt)
    ratio = request.video_ratio or ratio
    duration = request.video_duration or duration
    resolution = request.video_resolution or resolution
    args: list[str] = []
    if command == "text2video":
        args += ["--prompt", request.prompt]
    elif command == "image2video":
        args += ["--image", str(request.images[0]), "--prompt", request.prompt]
    elif command == "frames2video":
        args += ["--first", str(request.images[0]), "--last", str(request.images[1]), "--prompt", request.prompt]
    elif command == "multiframe2video":
        args += ["--images", ",".join(str(path) for path in request.images)]
        if len(request.images) == 2:
            args += ["--prompt", request.prompt]
            if duration:
                args += ["--duration", duration]
        else:
            for _ in range(len(request.images) - 1):
                args += ["--transition-prompt", request.prompt]
    elif command == "multimodal2video":
        for path in request.images:
            args += ["--image", str(path)]
        for path in request.videos:
            args += ["--video", str(path)]
        for path in request.audios:
            args += ["--audio", str(path)]
        # Dreamina binds multimodal references by repeated --image occurrence.
        # Make that contract explicit in the prompt so the model does not infer
        # a different semantic order from filenames or natural-language labels.
        args += ["--prompt", MULTIMODAL_IMAGE_ORDER_PREFIX + request.prompt]
    if command != "multiframe2video":
        args += ["--model_version", request.video_model or DEFAULT_VIDEO_MODEL, "--video_resolution", resolution or DEFAULT_VIDEO_RESOLUTION]
        if duration:
            args += ["--duration", duration]
        if ratio and command in ("text2video", "multimodal2video"):
            args += ["--ratio", ratio]
    args += ["--poll", "180"]
    return args


class VideoRouter:
    def __init__(self, config: dict, provider, store: TaskStore | None = None, duration_probe=audio_duration):
        self.config, self.provider, self.store, self.duration_probe = config, provider, store or TaskStore(), duration_probe

    def validate(self, request: MediaRequest) -> str:
        if not request.prompt.strip():
            raise ValueError("prompt must not be empty")
        command = select_video_command(request)
        if command == "multiframe2video":
            limits = ((request.images, 20, "images"),)
        elif command == "multimodal2video":
            selected_model = request.video_model or DEFAULT_VIDEO_MODEL
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
        audio_max_duration = 30 if (request.video_model or DEFAULT_VIDEO_MODEL) == DEFAULT_VIDEO_MODEL else 15
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
            lease = SlotLease(self.store.private_root / "locks" / "providers", self.provider.capacity_key, context.task_id, slots=self.provider.max_concurrency, cancel_path=context.cancelled_file)
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
                    final = MediaResult(context.task_id, "success", result.output_path, result.provider_id, result.model_id, [attempt])
                else:
                    failure = result.failure_class or FailureClass.INDETERMINATE_SUBMISSION
                    final = MediaResult(context.task_id, result.status, attempts=[attempt], failure_class=failure.value, safe_reason=result.safe_reason)
        self.store.set_state(context, final.status, failure_class=final.failure_class)
        self.store.write_result(context, final.to_dict())
        return final
