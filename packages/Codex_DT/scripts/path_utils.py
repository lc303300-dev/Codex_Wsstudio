"""Windows path handling shared by Codex_DT command-line entry points."""

from __future__ import annotations

import re
from pathlib import Path


def windows_path_candidates(value: str | Path) -> tuple[str, ...]:
    """Return the normalized spelling and safe underscore-join alternatives.

    A common Markdown/LLM escaping failure turns a folder such as
    ``SE_Work`` into the two path segments ``SE`` and ``_Work``.  The repaired
    spelling is only a *candidate*; callers must still verify that it exists
    before using it.
    """
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1]
    text = text.replace("/", "\\")
    if text.startswith("\\\\"):
        text = "\\\\" + re.sub(r"\\{2,}", lambda _: "\\", text[2:])
    else:
        text = re.sub(r"\\{2,}", lambda _: "\\", text)

    candidates = [text]
    # Join only a separator immediately before an underscore.  This handles
    # ``D:\\SE\\_Work`` -> ``D:\\SE_Work`` without changing unrelated
    # underscores or ordinary path separators.
    repaired = re.sub(r"(?<=[^\\])\\_", "_", text)
    if repaired != text:
        candidates.append(repaired)
    return tuple(dict.fromkeys(candidates))


def normalize_windows_path(value: str | Path) -> Path:
    """Restore a literal Windows path without losing ``_`` or path segments.

    Codex/PowerShell callers may provide quoted values, forward slashes, or
    JSON/Markdown-escaped runs of backslashes.  Normalize only separators;
    never treat underscores, spaces, or dots as formatting characters.
    """
    candidates = windows_path_candidates(value)
    path = Path(candidates[0])
    if not path.exists():
        for candidate in candidates[1:]:
            repaired_path = Path(candidate)
            if repaired_path.exists():
                return repaired_path
    return path


def canonical_path_text(value: str | Path) -> str:
    """Return a stable text representation suitable for logs/JSON/Markdown."""
    return normalize_windows_path(value).as_posix()
