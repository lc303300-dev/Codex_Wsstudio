from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


SECRET_PATTERNS = (
    re.compile(r"(?i)authorization\s*[:=]\s*(?:bearer\s+)?\S+"),
    re.compile(r"(?i)\bbearer\s+\S+"),
    re.compile(r"(?i)(?:api[_-]?key|cookie)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(?:access[_-]?token|refresh[_-]?token|session[_-]?token|device[_-]?code|user[_-]?code)\s*[:=]\s*\S+"),
)


def prompt_metadata(prompt: str) -> dict[str, Any]:
    return {
        "value": "<redacted>",
        "characters": len(prompt),
        "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }


def safe_text(value: str, limit: int = 400) -> str:
    cleaned = value.replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("<redacted>", cleaned)
    return cleaned[:limit]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
