from __future__ import annotations

from pathlib import Path

from .config import load_config
from .image_router import ImageRouter
from .providers.registry import build_registry
from .schemas import MediaRequest
from .video_router import VideoRouter


def execute(command: str, prompt: str, images=(), videos=(), audios=()) -> dict:
    config = load_config()
    registry = build_registry(config)
    request = MediaRequest(
        prompt.strip(),
        tuple(Path(path).resolve() for path in images),
        tuple(Path(path).resolve() for path in videos),
        tuple(Path(path).resolve() for path in audios),
    )
    if command == "generate_image":
        return ImageRouter(config, registry).execute(request).to_dict()
    if command == "generate_video":
        return VideoRouter(config, registry["dreamina-video"]).execute(request).to_dict()
    raise ValueError("Unknown media command")
