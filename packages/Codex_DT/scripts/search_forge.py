#!/usr/bin/env python3
"""Search the seedance-forge knowledge corpus through its native index search."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORGE_ROOT = ROOT / "third_party" / "seedance-forge"
DEFAULT_SEARCH = FORGE_ROOT / "scripts" / "search.py"
DEFAULT_INDEX = FORGE_ROOT / "references" / "indexes" / "combined.index.jsonl"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_index(index_path: Path) -> dict[str, dict[str, Any]]:
    """Load corpus records by id without interpreting model metadata as a filter."""
    rows: dict[str, dict[str, Any]] = {}
    with index_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {index_path}:{line_number}: {exc}") from exc
            row_id = str(row.get("id", ""))
            if row_id:
                rows[row_id] = row
    return rows


def run_native_search(search_script: Path, query: str, top: int) -> list[dict[str, Any]]:
    """Delegate ranking to seedance-forge's maintained native search implementation."""
    command = [sys.executable, str(search_script), query, "--top", str(top), "--json"]
    result = subprocess.run(
        command,
        cwd=search_script.parent.parent,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout or "[]")
    if not isinstance(payload, list):
        raise ValueError("seedance-forge native search returned a non-list JSON payload")
    return payload


def parse_author(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        return {"name": str(raw.get("name", "")), "link": str(raw.get("link", ""))}
    if not raw:
        return {"name": "", "link": ""}
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {"name": str(data.get("name", "")), "link": str(data.get("link", ""))}
        except json.JSONDecodeError:
            pass
    return {"name": str(raw), "link": ""}


def compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def native_score(row: dict[str, Any], query: str) -> int:
    """Mirror the native search score so the legacy wrapper payload keeps `score`."""
    title = str(row.get("title") or "").lower()
    category = str(row.get("category") or "").lower()
    description = str(row.get("description") or "").lower()
    content = str(row.get("content") or "").lower()
    return sum(
        title.count(keyword) * 4
        + category.count(keyword) * 3
        + description.count(keyword) * 2
        + content.count(keyword)
        for keyword in (part.lower() for part in query.split())
    )


def row_payload(
    row: dict[str, Any], include_content: bool, preview_chars: int, score: int = 0
) -> dict[str, Any]:
    content = str(row.get("content", ""))
    source_model = str(row.get("seedance_version", ""))
    payload: dict[str, Any] = {
        "id": str(row.get("id", "")),
        "title": str(row.get("title", "")),
        "description": str(row.get("description", "")),
        "score": score,
        "length": len(content),
        "author": parse_author(row.get("author", "")),
        "sourceLink": str(row.get("sourceLink", "")),
        "sourcePublishedAt": str(row.get("sourcePublishedAt", "")),
        "source_project": str(row.get("source_project", "")),
        "source_model": source_model,
        "source_metadata": {
            "model": source_model,
            "repository": str(row.get("source_repo", "")),
            "license": str(row.get("source_license", "")),
        },
        "content_preview": compact(content, preview_chars),
    }
    if include_content:
        payload["content"] = content
    return payload


def query_from_manifest(manifest: dict[str, Any]) -> str:
    forge = manifest.get("forge", {})
    parts: list[str] = []
    for key in ("queries_en", "queries_zh"):
        value = forge.get(key, [])
        if isinstance(value, list):
            parts.extend(str(item) for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            parts.append(value)
    if parts:
        return " ".join(parts)

    visual = manifest.get("visual", {})
    motion = manifest.get("motion_plan", {})
    fallback_parts = [
        manifest.get("photo_type", ""),
        visual.get("description_zh", ""),
        motion.get("camera_motion_zh", ""),
    ]
    return " ".join(str(part) for part in fallback_parts if str(part).strip())


def search(
    query: str,
    top: int,
    search_script: Path = DEFAULT_SEARCH,
    index_path: Path = DEFAULT_INDEX,
) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    native_matches = run_native_search(search_script, query, top)
    rows_by_id = load_index(index_path)
    # Native search owns ranking. The index is only used to restore full records and
    # provenance; source model/version is intentionally never used as a constraint.
    return [rows_by_id[item_id] for item in native_matches if (item_id := str(item.get("id", ""))) in rows_by_id]


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the general video-prompt corpus via seedance-forge.")
    parser.add_argument("query", nargs="?", help="Search keywords. Ignored when --manifest supplies forge queries.")
    parser.add_argument("--manifest", type=Path, help="Read queries from a pipeline manifest.")
    parser.add_argument("--search-script", type=Path, default=DEFAULT_SEARCH, help="Native seedance-forge search.py.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="Path to combined.index.jsonl.")
    parser.add_argument("--top", type=int, default=5, help="Number of results.")
    parser.add_argument("--preview-chars", type=int, default=500, help="Preview length for each match.")
    parser.add_argument("--include-content", action="store_true", help="Include complete prompt content.")
    parser.add_argument("--out", type=Path, help="Optional JSON output file.")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    query = args.query or ""
    manifest_id = None
    if args.manifest:
        manifest = read_json(args.manifest)
        manifest_id = manifest.get("id")
        query = query_from_manifest(manifest)

    rows = search(query, args.top, args.search_script, args.index)
    matches = [
        row_payload(row, args.include_content, args.preview_chars, native_score(row, query))
        for row in rows
    ]
    payload = {
        "query": query,
        "manifest_id": manifest_id,
        "top": args.top,
        "count": len(matches),
        "matches": matches,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
