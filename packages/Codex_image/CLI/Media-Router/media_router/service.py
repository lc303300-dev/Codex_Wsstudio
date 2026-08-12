from __future__ import annotations

from pathlib import Path

from .config import load_config
from .image_router import ImageRouter
from .providers.registry import build_registry
from .schemas import MediaRequest
from .video_router import VideoRouter


def execute(command: str, prompt: str, images=(), videos=(), audios=(), **video_options) -> dict:
    config = load_config()
    registry = build_registry(config)
    request = MediaRequest(
        prompt.strip(),
        tuple(Path(path).resolve() for path in images),
        tuple(Path(path).resolve() for path in videos),
        tuple(Path(path).resolve() for path in audios),
        video_command=video_options.get("video_command"),
        video_model=video_options.get("video_model"),
        video_ratio=video_options.get("video_ratio"),
        video_duration=video_options.get("video_duration"),
        video_resolution=video_options.get("video_resolution"),
        image_provider=video_options.get("image_provider"),
        image_model=video_options.get("image_model"),
    )
    if command == "generate_image":
        return ImageRouter(config, registry).execute(request).to_dict()
    if command == "generate_video":
        return VideoRouter(config, registry["dreamina-video"]).execute(request).to_dict()
    raise ValueError("Unknown media command")
