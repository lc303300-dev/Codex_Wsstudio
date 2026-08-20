from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import replace
from pathlib import Path

from .config import PROJECT_ROOT
from .schemas import MediaRequest, TaskContext


RESIZE_SCRIPT = PROJECT_ROOT / "CLI" / "Media-Router" / "resize-provider-image.ps1"
PILLOW_RESIZE_SCRIPT = PROJECT_ROOT / "CLI" / "Media-Router" / "resize_provider_image.py"
MAX_PROVIDER_IMAGE_LONG_EDGE = 1920
MAX_PROVIDER_IMAGE_BYTES = 4_500_000


def _resize_command(source: Path, output: Path, metadata: Path, max_long_edge: int) -> list[str]:
    bundled_python = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python" / "python.exe"
    if os.name == "nt" and bundled_python.is_file():
        return [
            str(bundled_python), "-B", str(PILLOW_RESIZE_SCRIPT),
            "--input", str(source), "--output", str(output), "--metadata", str(metadata),
            "--max-long-edge", str(max_long_edge), "--max-bytes", str(MAX_PROVIDER_IMAGE_BYTES),
        ]
    return [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(RESIZE_SCRIPT),
        "-InputPath", str(source), "-OutputPath", str(output), "-MetadataPath", str(metadata),
        "-MaxLongEdge", str(max_long_edge),
    ]


def prepare_provider_images(
    request: MediaRequest,
    context: TaskContext,
    max_long_edge: int,
    deadline: float | None = None,
) -> MediaRequest:
    if not request.images:
        return request

    input_dir = context.job_dir / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    provider_images: list[Path] = []

    for index, source in enumerate(request.images, 1):
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("Image input preparation exceeded the task deadline")
        output = input_dir / f"image-{index}.png"
        metadata = input_dir / f"image-{index}.json"
        timeout = max(0.001, deadline - time.monotonic()) if deadline is not None else 60.0
        command = _resize_command(source, output, metadata, max_long_edge)
        try:
            completed = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"Cannot prepare provider image: {source}") from exc
        if completed.returncode or not metadata.is_file():
            raise ValueError(f"Cannot prepare provider image: {source}")
        try:
            details = json.loads(metadata.read_text(encoding="utf-8-sig"))
            provider_path = Path(details["provider_path"]).resolve()
            width = int(details["provider_width"])
            height = int(details["provider_height"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid provider image metadata: {source}") from exc
        if not provider_path.is_file() or max(width, height) > max_long_edge:
            raise ValueError(f"Provider image exceeds the {max_long_edge}px limit: {source}")
        if provider_path.stat().st_size > MAX_PROVIDER_IMAGE_BYTES:
            raise ValueError(f"Provider image exceeds the {MAX_PROVIDER_IMAGE_BYTES}-byte limit after compression: {source}")
        provider_images.append(provider_path)

    return replace(request, images=tuple(provider_images))
