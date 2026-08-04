#!/usr/bin/env python3
"""Shared helpers for per-image subagent dispatch state."""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from runtime_paths import existing_runtime_path, migrate_legacy_runtime_file, runtime_path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_STATUSES = {"dispatched"}
DISPATCHABLE_STATUSES = {"pending"}
DEFAULT_MAX_CONCURRENT_IMAGES = 3
LOCK_TIMEOUT_SECONDS = 30
LOCK_POLL_SECONDS = 0.1
STALE_LOCK_SECONDS = 600


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel_to_root(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def resolve_workspace_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def jobs_path(batch: str) -> Path:
    return existing_runtime_path(
        batch,
        "image_jobs.json",
        legacy_parts=("outputs", batch, "image_jobs.json"),
    )


def lock_path(batch: str) -> Path:
    return runtime_path(batch, "image_jobs.lock")


def load_jobs(batch: str) -> dict[str, Any]:
    return read_json(jobs_path(batch))


def save_jobs(batch: str, jobs: dict[str, Any]) -> None:
    jobs["updated_at"] = now_iso()
    write_json(runtime_path(batch, "image_jobs.json"), jobs)


def acquire_jobs_lock(batch: str, timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> Path:
    path = lock_path(batch)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
                if age > STALE_LOCK_SECONDS:
                    path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for image job lock: {path}")
            time.sleep(LOCK_POLL_SECONDS)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "created_at": now_iso()}, ensure_ascii=False) + "\n")
        return path


def release_jobs_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


@contextmanager
def locked_jobs(batch: str, timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> Iterator[dict[str, Any]]:
    path = acquire_jobs_lock(batch, timeout_seconds)
    try:
        migrate_legacy_runtime_file(
            batch,
            "image_jobs.json",
            legacy_parts=("outputs", batch, "image_jobs.json"),
        )
        jobs = load_jobs(batch)
        yield jobs
        save_jobs(batch, jobs)
    finally:
        release_jobs_lock(path)


def find_image(jobs: dict[str, Any], image_id: str) -> dict[str, Any]:
    for image in jobs.get("images", []):
        if image.get("id") == image_id:
            return image
    raise KeyError(f"Image job not found: {image_id}")


def active_images(jobs: dict[str, Any]) -> list[dict[str, Any]]:
    return [image for image in jobs.get("images", []) if image.get("status") in ACTIVE_STATUSES]


def dispatchable_images(jobs: dict[str, Any]) -> list[dict[str, Any]]:
    return [image for image in jobs.get("images", []) if image.get("status") in DISPATCHABLE_STATUSES]


def max_concurrent_images(jobs: dict[str, Any]) -> int:
    value = jobs.get("max_concurrent_images", DEFAULT_MAX_CONCURRENT_IMAGES)
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid max_concurrent_images: {value}") from exc
    if value < 1:
        raise ValueError("max_concurrent_images must be >= 1")
    return value


def dispatch_slots_available(jobs: dict[str, Any]) -> int:
    return max(0, max_concurrent_images(jobs) - len(active_images(jobs)))


def update_run_status(jobs: dict[str, Any]) -> None:
    images = jobs.get("images", [])
    if not images:
        jobs["run_status"] = "tasks_recorded"
    elif all(image.get("status") == "recorded" for image in images):
        jobs["run_status"] = "images_recorded"
    elif all(image.get("status") in {"dispatched", "recorded"} for image in images):
        jobs["run_status"] = "images_dispatched"
    elif any(image.get("status") == "dispatched" for image in images):
        jobs["run_status"] = "images_in_progress"
    elif any(image.get("status") == "pending" for image in images):
        jobs["run_status"] = "tasks_recorded"
    else:
        jobs["run_status"] = "mixed"
    jobs["updated_at"] = now_iso()
