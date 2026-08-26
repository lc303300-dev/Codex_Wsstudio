"""Windows path handling shared by Codex_DT command-line entry points."""

from __future__ import annotations

import re
from pathlib import Path


def normalize_windows_path(value: str | Path) -> Path:
    """Restore a literal Windows path without losing ``_`` or path segments.

    Codex/PowerShell callers may provide quoted values, forward slashes, or
    JSON/Markdown-escaped runs of backslashes.  Normalize only separators;
    never treat underscores, spaces, or dots as formatting characters.
    """
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1]
    text = text.replace("/", "\\")
    # Preserve UNC's two leading separators, collapse accidental escaping in
    # the remainder (e.g. D:\\SE\\_Work\\\\clip.png).
    if text.startswith("\\\\"):
        text = "\\\\" + re.sub(r"\\{2,}", lambda _: "\\", text[2:])
    else:
        text = re.sub(r"\\{2,}", lambda _: "\\", text)
    return Path(text)


def canonical_path_text(value: str | Path) -> str:
    """Return a stable text representation suitable for logs/JSON/Markdown."""
    return normalize_windows_path(value).as_posix()
