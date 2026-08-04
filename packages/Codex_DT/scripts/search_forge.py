#!/usr/bin/env python3
"""Search the local seedance-forge corpus and return full prompt matches."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

csv.field_size_limit(10_000_000)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "third_party" / "seedance-forge" / "references" / "seedance-prompts.csv"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_author(raw: str) -> dict[str, str]:
    if not raw:
        return {"name": "", "link": ""}
    try:
        data = json.loads(raw)
        return {"name": str(data.get("name", "")), "link": str(data.get("link", ""))}
    except json.JSONDecodeError:
        return {"name": raw, "link": ""}


def tokenize_query(query: str) -> list[str]:
    normalized = re.sub(r"[,\n\r\t;/|]+", " ", query).strip()
    return [token.lower() for token in normalized.split() if token.strip()]


def score_row(row: dict[str, str], keywords: list[str]) -> int:
    title = row.get("title", "").lower()
    description = row.get("description", "").lower()
    content = row.get("content", "").lower()
    score = 0
    for keyword in keywords:
        score += title.count(keyword) * 5
        score += description.count(keyword) * 3
        score += content.count(keyword)
    return score


def compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def row_payload(row: dict[str, str], score: int, include_content: bool, preview_chars: int) -> dict[str, Any]:
    content = row.get("content", "")
    payload: dict[str, Any] = {
        "id": row.get("id", ""),
        "title": row.get("title", ""),
        "description": row.get("description", ""),
        "score": score,
        "length": len(content),
        "author": parse_author(row.get("author", "")),
        "sourceLink": row.get("sourceLink", ""),
        "sourcePublishedAt": row.get("sourcePublishedAt", ""),
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
        elif isinstance(value, str):
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


def search(rows: list[dict[str, str]], query: str, top: int) -> list[tuple[int, dict[str, str]]]:
    keywords = tokenize_query(query)
    if not keywords:
        return []
    scored = [(score_row(row, keywords), row) for row in rows]
    scored = [(score, row) for score, row in scored if score > 0]
    scored.sort(key=lambda item: (-item[0], len(item[1].get("content", ""))))
    return scored[:top]


def main() -> int:
    parser = argparse.ArgumentParser(description="Search seedance-forge with full prompt output.")
    parser.add_argument("query", nargs="?", help="Search keywords. Ignored when --manifest supplies forge queries.")
    parser.add_argument("--manifest", type=Path, help="Read queries from a pipeline manifest.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to seedance-prompts.csv.")
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

    rows = load_rows(args.csv)
    matches = [
        row_payload(row, score, args.include_content, args.preview_chars)
        for score, row in search(rows, query, args.top)
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
