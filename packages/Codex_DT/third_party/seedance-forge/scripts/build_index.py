#!/usr/bin/env python3
"""Build a disposable search index from every decoupled Seedance source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
SOURCES = REFERENCES / "sources"
INDEXES = REFERENCES / "indexes"

csv.field_size_limit(10_000_000)


def normalize_ws(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", (text or "").strip())


def content_hash(text: str) -> str:
    normalized = normalize_ws(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def parse_author(raw: str | dict | None) -> dict:
    if isinstance(raw, dict):
        return {"name": raw.get("name", ""), "link": raw.get("link", "")}
    if not raw:
        return {"name": "", "link": ""}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {"name": data.get("name", ""), "link": data.get("link", "")}
    except Exception:
        pass
    return {"name": str(raw), "link": ""}


def load_manifest(source_dir: Path) -> dict:
    path = source_dir / "manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"source_id": source_dir.name, "license": "", "repo": ""}


def rows_from_csv(source_dir: Path, manifest: dict) -> list[dict]:
    path = source_dir / manifest.get("path", "prompts.csv")
    rows = []
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            item = {
                "id": f"{manifest['source_id']}-{row.get('id', content_hash(row.get('content', '')))}",
                "title": row.get("title", ""),
                "description": row.get("description", ""),
                "content": row.get("content", ""),
                "language": row.get("language", ""),
                "seedance_version": row.get("seedance_version", "2.0"),
                "source_project": manifest["source_id"],
                "source_repo": manifest.get("repo", ""),
                "source_commit": manifest.get("source_commit", ""),
                "source_license": manifest.get("license", ""),
                "sourceLink": row.get("sourceLink", ""),
                "sourcePublishedAt": row.get("sourcePublishedAt", ""),
                "author": parse_author(row.get("author", "")),
                "sourceMedia": row.get("sourceMedia", ""),
                "sourceReferenceImages": row.get("sourceReferenceImages", ""),
                "sourceVideos": row.get("sourceVideos", ""),
                "contentHash": content_hash(row.get("content", "")),
            }
            rows.append(item)
    return rows


def rows_from_jsonl(source_dir: Path, manifest: dict) -> list[dict]:
    path = source_dir / manifest.get("path", "prompts.jsonl")
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            row.setdefault("source_project", manifest["source_id"])
            row.setdefault("source_repo", manifest.get("repo", ""))
            row.setdefault("source_license", manifest.get("license", ""))
            row.setdefault("contentHash", content_hash(row.get("content", "")))
            rows.append(row)
    return rows


def load_all() -> list[dict]:
    rows = []
    for source_dir in sorted(SOURCES.iterdir()):
        if not source_dir.is_dir():
            continue
        manifest = load_manifest(source_dir)
        source_type = manifest.get("type")
        if source_type == "csv":
            rows.extend(rows_from_csv(source_dir, manifest))
        elif source_type == "jsonl":
            rows.extend(rows_from_jsonl(source_dir, manifest))
    return rows


def mark_duplicates(rows: list[dict]) -> tuple[list[dict], int]:
    seen: dict[str, str] = {}
    duplicate_count = 0
    for row in rows:
        keys = [row.get("sourceLink") or "", row.get("contentHash") or ""]
        duplicate_of = ""
        for key in keys:
            if key and key in seen:
                duplicate_of = seen[key]
                break
        if duplicate_of:
            row["duplicate_of"] = duplicate_of
            duplicate_count += 1
        else:
            row["duplicate_of"] = ""
            for key in keys:
                if key:
                    seen[key] = row["id"]
    return rows, duplicate_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Build combined Seedance prompt search index.")
    parser.add_argument("--include-duplicates", action="store_true", help="Keep duplicate rows searchable.")
    args = parser.parse_args()

    INDEXES.mkdir(parents=True, exist_ok=True)
    rows, duplicate_count = mark_duplicates(load_all())
    searchable = rows if args.include_duplicates else [row for row in rows if not row.get("duplicate_of")]
    index_path = INDEXES / "combined.index.jsonl"
    with index_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in searchable:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    stats = {
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "total_rows": len(rows),
        "searchable_rows": len(searchable),
        "duplicate_rows": duplicate_count,
        "sources": {},
    }
    for row in rows:
        source = row.get("source_project", "unknown")
        stats["sources"][source] = stats["sources"].get(source, 0) + 1
    (INDEXES / "combined.stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
