from __future__ import annotations

from pathlib import Path
import re


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

from .config import load_config
from .image_router import ImageRouter
from .providers.registry import build_registry
from .schemas import MediaRequest
from .video_router import VideoRouter


def execute(command: str, prompt: str, images=(), videos=(), audios=(), **video_options) -> dict:
    # Fail closed at the provider boundary. Never try to repair or strip a
    # shell/tool wrapper: doing so could turn a polluted, truncated payload
    # into something that looks valid enough to consume credits.
    validate_prompt_completeness(prompt)
    config = load_config()
    registry = build_registry(config)
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
        video_duration=video_options.get("video_duration"),
        video_resolution=video_options.get("video_resolution"),
        image_provider=video_options.get("image_provider"),
        image_model=video_options.get("image_model"),
        image_ratio=video_options.get("image_ratio"),
        image_resolution=video_options.get("image_resolution", "1K"),
    )
    if command == "generate_image":
        return ImageRouter(config, registry).execute(request).to_dict()
    if command == "generate_video":
        return VideoRouter(config, registry["dreamina-video"]).execute(request).to_dict()
    raise ValueError("Unknown media command")
