"""Resolve private runtime paths while keeping legacy batches readable."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_RUNTIME_ROOT = ROOT / ".codex-image-private"


def batch_runtime_dir(batch: str) -> Path:
    return PRIVATE_RUNTIME_ROOT / "batches" / batch


def runtime_path(batch: str, *parts: str) -> Path:
    return batch_runtime_dir(batch).joinpath(*parts)


def existing_runtime_path(batch: str, *parts: str, legacy_parts: tuple[str, ...] | None = None) -> Path:
    """Prefer the private path and fall back to a pre-migration location."""
    private = runtime_path(batch, *parts)
    if private.exists() or legacy_parts is None:
        return private
    legacy = ROOT.joinpath(*legacy_parts)
    return legacy if legacy.exists() else private


def migrate_legacy_runtime_file(batch: str, *parts: str, legacy_parts: tuple[str, ...]) -> Path:
    """Copy legacy state into private runtime before the next write."""
    private = runtime_path(batch, *parts)
    legacy = ROOT.joinpath(*legacy_parts)
    if not private.exists() and legacy.is_file():
        private.parent.mkdir(parents=True, exist_ok=True)
        private.write_bytes(legacy.read_bytes())
    return private
