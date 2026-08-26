#!/usr/bin/env python3
"""Create an isolated batch directory set and optionally copy source images."""

from __future__ import annotations

import argparse
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from path_utils import normalize_windows_path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_RUNTIME_ROOT = ROOT / ".codex-image-private" / "batches"
BATCH_ROOTS = ("inputs", "previews", "manifests", "prompts", "review", "outputs")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".heic", ".heif"}
TIMESTAMP_FORMAT = "%Y%m%d-%H%M"
DEFAULT_WAIT_TIMEOUT_SECONDS = 90.0
DEFAULT_STABLE_SECONDS = 1.5
POLL_SECONDS = 0.25


def safe_batch_id(value: str) -> str:
    value = value.strip()
    if not value:
        value = datetime.now().strftime(TIMESTAMP_FORMAT)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
    if not safe:
        raise SystemExit("Batch id must contain at least one letter or number.")
    return safe


def timestamped_batch_id(name: str) -> str:
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    suffix = safe_batch_id(name)
    return f"{timestamp}-{suffix}"


def next_image_name(index: int, source: Path) -> str:
    suffix = source.suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise SystemExit(f"Unsupported image extension for {source}")
    return f"image{index}{suffix}"


def wait_for_stable_file(path: Path, timeout_seconds: float, stable_seconds: float) -> Path:
    """Wait until an app-provided attachment path exists and stops changing."""
    deadline = time.monotonic() + timeout_seconds
    last_size: int | None = None
    stable_since: float | None = None
    last_error: OSError | None = None

    while time.monotonic() <= deadline:
        try:
            resolved = path.expanduser().resolve(strict=False)
            stat = resolved.stat()
            if not resolved.is_file():
                last_error = None
                time.sleep(POLL_SECONDS)
                continue

            size = stat.st_size
            if size <= 0:
                last_size = size
                stable_since = None
                time.sleep(POLL_SECONDS)
                continue

            with resolved.open("rb"):
                pass

            now = time.monotonic()
            if size != last_size:
                last_size = size
                stable_since = now
            elif stable_since is not None and now - stable_since >= stable_seconds:
                return resolved
            elif stable_since is None:
                stable_since = now
        except OSError as exc:
            last_error = exc
            last_size = None
            stable_since = None
        time.sleep(POLL_SECONDS)

    detail = f" Last error: {last_error}" if last_error else ""
    raise SystemExit(f"Image did not become readable and stable within {timeout_seconds:g}s: {path}.{detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create per-task pipeline folders under inputs/previews/manifests/prompts/review/outputs.")
    parser.add_argument("--batch", help="Batch/task id. Defaults to timestamp with current hour and minute.")
    parser.add_argument("--name", help="Descriptive suffix. The final batch id is YYYYMMDD-HHMM-<name>.")
    parser.add_argument("--images", nargs="*", default=[], help="Optional source images to copy into inputs/<batch>/ as image1.ext, image2.ext, ...")
    parser.add_argument("--force", action="store_true", help="Allow copying over an existing image name in inputs/<batch>.")
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not wait for image paths to become readable and size-stable before copying.",
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=DEFAULT_WAIT_TIMEOUT_SECONDS,
        help=f"Seconds to wait for each image path when attachments are still landing. Default: {DEFAULT_WAIT_TIMEOUT_SECONDS:g}.",
    )
    parser.add_argument(
        "--stable-seconds",
        type=float,
        default=DEFAULT_STABLE_SECONDS,
        help=f"Required unchanged file-size window before copying. Default: {DEFAULT_STABLE_SECONDS:g}.",
    )
    args = parser.parse_args()

    if args.batch and args.name:
        raise SystemExit("Use either --batch or --name, not both.")
    batch = timestamped_batch_id(args.name) if args.name else safe_batch_id(args.batch or "")
    created: list[Path] = []
    for name in BATCH_ROOTS:
        path = ROOT / name / batch
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)
    (ROOT / "outputs" / batch / "videos").mkdir(parents=True, exist_ok=True)
    (PRIVATE_RUNTIME_ROOT / batch).mkdir(parents=True, exist_ok=True)

    copied = 0
    for index, raw_source in enumerate(args.images, start=1):
        source = normalize_windows_path(raw_source)
        if args.no_wait:
            resolved = source.expanduser().resolve()
            if not resolved.is_file():
                raise SystemExit(f"Image not found: {source}")
        else:
            resolved = wait_for_stable_file(source, args.wait_timeout, args.stable_seconds)
        dest = ROOT / "inputs" / batch / next_image_name(index, resolved)
        if dest.exists() and not args.force:
            raise SystemExit(f"Destination already exists: {dest}. Re-run with --force to overwrite.")
        shutil.copy2(resolved, dest)
        copied += 1

    print(f"batch={batch}")
    print("created:")
    for path in created:
        print(f"  {path.relative_to(ROOT).as_posix()}/")
    print(f"copied_images={copied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
