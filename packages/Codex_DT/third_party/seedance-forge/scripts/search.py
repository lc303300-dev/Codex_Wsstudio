#!/usr/bin/env python3
"""Search the decoupled Seedance prompt index."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "references" / "indexes" / "combined.index.jsonl"


def load_rows(index_path: Path = INDEX_PATH) -> list[dict]:
    if not index_path.exists():
        print(
            f"Error: index not found at {index_path}. Run scripts/build_index.py first.",
            file=sys.stderr,
        )
        sys.exit(1)
    rows = []
    with index_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def parse_author(raw) -> tuple[str, str]:
    if isinstance(raw, dict):
        return raw.get("name", ""), raw.get("link", "")
    return str(raw or ""), ""


def score_row(row: dict, keywords: list[str]) -> int:
    title = (row.get("title") or "").lower()
    desc = (row.get("description") or "").lower()
    category = (row.get("category") or "").lower()
    content = (row.get("content") or "").lower()
    score = 0
    for kw in keywords:
        kw = kw.lower()
        score += title.count(kw) * 4
        score += category.count(kw) * 3
        score += desc.count(kw) * 2
        score += content.count(kw)
    return score


def apply_filters(rows: list[dict], args: argparse.Namespace) -> list[dict]:
    result = []
    source_filter = None
    if args.source:
        source_filter = {item.strip().lower() for item in args.source.split(",") if item.strip()}
    for row in rows:
        content = row.get("content") or ""
        length = len(content)
        if args.min_length and length < args.min_length:
            continue
        if args.max_length and length > args.max_length:
            continue
        if args.author:
            name, _ = parse_author(row.get("author", ""))
            if args.author.lower() not in name.lower():
                continue
        if source_filter and (row.get("source_project") or "").lower() not in source_filter:
            continue
        if args.language and (row.get("language") or "").lower() != args.language.lower():
            continue
        result.append(row)
    return result


def format_human(rank: int, row: dict) -> str:
    name, link = parse_author(row.get("author", ""))
    length = len(row.get("content") or "")
    title = row.get("title", "")
    source = row.get("source_project", "")
    preview = (row.get("content") or "").replace("\n", " ").replace("\r", " ")
    if len(preview) > 300:
        preview = preview[:300] + "..."
    author_line = f"    by {name}" if name else "    by unknown"
    if link:
        author_line += f" — {link}"
    lines = [
        f"[{rank}] id={row.get('id', '')} | source={source} | len={length} | \"{title}\"",
        author_line,
        f"    {preview}",
    ]
    source_link = row.get("sourceLink") or ""
    if source_link:
        lines.append(f"    sourceLink: {source_link}")
    return "\n".join(lines)


def format_json_obj(row: dict) -> dict:
    name, _ = parse_author(row.get("author", ""))
    preview = (row.get("content") or "").replace("\n", " ").replace("\r", " ")[:300]
    return {
        "id": row.get("id", ""),
        "source_project": row.get("source_project", ""),
        "title": row.get("title", ""),
        "length": len(row.get("content") or ""),
        "author": name,
        "sourceLink": row.get("sourceLink", ""),
        "content_preview": preview,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Seedance prompt sources")
    parser.add_argument("query", nargs="?", help="Keywords to search for")
    parser.add_argument("--top", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--author", type=str, default=None, help="Filter by author name")
    parser.add_argument("--source", type=str, default=None, help="Comma-separated source IDs, e.g. youmind,zerolu")
    parser.add_argument("--language", type=str, default=None, help="Filter by language tag.")
    parser.add_argument("--min-length", type=int, default=None, dest="min_length")
    parser.add_argument("--max-length", type=int, default=None, dest="max_length")
    parser.add_argument("--random", type=int, default=None, metavar="N", dest="random_n")
    parser.add_argument("--json", action="store_true", dest="json_out")
    args = parser.parse_args()

    rows = load_rows()
    filtered = apply_filters(rows, args)

    if args.random_n is not None:
        n = args.random_n
        if n > len(filtered):
            print(f"Warning: requested {n} but only {len(filtered)} rows after filters. Returning all.", file=sys.stderr)
            results = filtered
        else:
            results = random.sample(filtered, n)
    elif args.query:
        keywords = args.query.split()
        scored = [(score_row(row, keywords), len(row.get("content") or ""), row) for row in filtered]
        scored = [(s, l, r) for s, l, r in scored if s > 0]
        scored.sort(key=lambda x: (-x[0], x[1]))
        results = [r for _, _, r in scored[: args.top]]
    elif args.author or args.source or args.language:
        results = filtered[: args.top]
    else:
        parser.print_help()
        return 0

    if not results:
        print("[]" if args.json_out else "No results found.")
        return 0

    if args.json_out:
        print(json.dumps([format_json_obj(r) for r in results], ensure_ascii=False, indent=2))
    else:
        for i, row in enumerate(results, 1):
            print(format_human(i, row))
            if i < len(results):
                print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
