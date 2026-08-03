from __future__ import annotations

import os
import tempfile
from pathlib import Path


IMAGE_SIGNATURES = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM", b"\x00\x00\x01\x00")


def is_valid_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    with path.open("rb") as stream:
        prefix = stream.read(16)
    return prefix.startswith(IMAGE_SIGNATURES) or (prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP")


def is_valid_video(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    with path.open("rb") as stream:
        prefix = stream.read(16)
    return prefix.startswith(b"\x1aE\xdf\xa3") or (prefix.startswith(b"RIFF") and prefix[8:12] == b"AVI ") or prefix[4:8] == b"ftyp"


def atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
