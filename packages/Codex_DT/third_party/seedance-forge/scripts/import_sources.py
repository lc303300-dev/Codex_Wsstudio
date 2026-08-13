#!/usr/bin/env python3
"""Import decoupled Seedance prompt sources into source-local JSONL files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
SOURCES = REFERENCES / "sources"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def content_hash(text: str) -> str:
    normalized = normalize_ws(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def detect_language(text: str) -> str:
    cjk = len(re.findall(r"[\u3400-\u9fff]", text or ""))
    latin = len(re.findall(r"[A-Za-z]", text or ""))
    if cjk and latin:
        return "mixed" if min(cjk, latin) > max(cjk, latin) * 0.15 else ("zh" if cjk > latin else "en")
    if cjk:
        return "zh"
    if latin:
        return "en"
    return ""


def repo_commit(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except Exception:
        return ""


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def update_manifest(source_id: str, *, commit: str, count: int, imported_at: str) -> None:
    path = SOURCES / source_id / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source_commit"] = commit
    data["record_count"] = count
    data["imported_at"] = imported_at
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_author_link(raw: str) -> tuple[str, str]:
    match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", raw or "")
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return normalize_ws(raw), ""


def markdown_code_blocks(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"(?s)```(?:text)?\s*\r?\n(.*?)\r?\n```", text)]


def import_youmind(repo: Path, imported_at: str) -> int:
    readme = repo / "README_zh.md"
    text = readme.read_text(encoding="utf-8", errors="replace")
    commit = repo_commit(repo)
    rows = []
    pattern = re.compile(
        r"(?ms)^###\s+(?P<title>.+?)\r?\n"
        r".*?####\s+📝\s+提示词\s*\r?\n```(?:text)?\s*\r?\n(?P<content>.*?)\r?\n```"
        r"(?P<tail>.*?)(?=^###\s+|\Z)"
    )
    for index, match in enumerate(pattern.finditer(text), start=1):
        title = normalize_ws(match.group("title"))
        content = match.group("content").strip()
        tail = match.group("tail")
        description = ""
        desc_match = re.search(r"(?ms)####\s+📖\s+描述\s*\r?\n(.*?)(?=####\s+📝\s+提示词)", match.group(0))
        if desc_match:
            description = normalize_ws(desc_match.group(1))
        author_name = ""
        author_link = ""
        author_match = re.search(r"\*\*作者:\*\*\s*(.*?)(?:\s*\|\s*|\r?\n)", tail)
        if author_match:
            author_name, author_link = parse_author_link(author_match.group(1))
        source_link = ""
        source_match = re.search(r"\*\*来源:\*\*\s*\[Link\]\(([^)]+)\)", tail)
        if source_match:
            source_link = source_match.group(1).strip()
        published_at = ""
        published_match = re.search(r"\*\*发布时间:\*\*\s*([^\r\n]+)", tail)
        if published_match:
            published_at = normalize_ws(published_match.group(1))
        videos = re.findall(r"https?://[^\s)]+?\.mp4(?:\?[^\s)]*)?", tail)
        row_id = f"youmind-{content_hash(source_link or content)}"
        rows.append(
            {
                "id": row_id,
                "title": title,
                "description": description,
                "content": content,
                "language": detect_language(content),
                "seedance_version": "2.0",
                "source_project": "youmind",
                "source_repo": "https://github.com/YouMind-OpenLab/awesome-seedance-2-prompts",
                "source_commit": commit,
                "source_license": "CC BY 4.0",
                "sourceLink": source_link,
                "sourcePublishedAt": published_at,
                "author": {"name": author_name, "link": author_link},
                "sourceMedia": [],
                "sourceReferenceImages": [],
                "sourceVideos": videos,
                "contentHash": content_hash(content),
                "importedAt": imported_at,
                "sourceOrdinal": index,
            }
        )
    count = write_jsonl(SOURCES / "youmind" / "prompts.jsonl", rows)
    update_manifest("youmind", commit=commit, count=count, imported_at=imported_at)
    return count


def section_category(prefix: list[str]) -> str:
    return " > ".join(item for item in prefix if item)


def import_zerolu(repo: Path, imported_at: str) -> int:
    commit = repo_commit(repo)
    markdown_files = [repo / "README-zh.md", *sorted((repo / "prompts").glob("*.md"))]
    rows = []
    ordinal = 0
    for md_path in markdown_files:
        if not md_path.exists():
            continue
        text = md_path.read_text(encoding="utf-8", errors="replace")
        headings: list[tuple[int, str, int, int]] = []
        for match in re.finditer(r"(?m)^(#{2,4})\s+(.+?)\s*$", text):
            headings.append((len(match.group(1)), normalize_ws(match.group(2)), match.start(), match.end()))
        headings.append((0, "", len(text), len(text)))
        context: list[str] = []
        for pos, (level, title, _start, end) in enumerate(headings[:-1]):
            next_start = headings[pos + 1][2]
            while len(context) >= max(0, level - 1):
                context.pop()
            context.append(title)
            segment = text[end:next_start]
            blocks = markdown_code_blocks(segment)
            if not blocks:
                continue
            source_link = ""
            source_match = re.search(r"来源[:：].*?\((https?://[^)]+)\)", segment)
            if source_match:
                source_link = source_match.group(1).strip()
            author_name = ""
            author_link = ""
            author_match = re.search(r"来源[:：]\s*([^\-\n*]+)", segment)
            if author_match:
                author_name = normalize_ws(author_match.group(1))
            for block in blocks:
                if len(block) < 8:
                    continue
                ordinal += 1
                row_id = f"zerolu-{content_hash(source_link + block)}"
                rows.append(
                    {
                        "id": row_id,
                        "title": title,
                        "description": "",
                        "content": block,
                        "language": detect_language(block),
                        "seedance_version": "2.0",
                        "category": section_category(context[:-1]),
                        "source_project": "zerolu",
                        "source_repo": "https://github.com/ZeroLu/awesome-seedance",
                        "source_commit": commit,
                        "source_license": "MIT",
                        "sourceLink": source_link,
                        "sourcePublishedAt": "",
                        "author": {"name": author_name, "link": author_link},
                        "sourceMedia": [],
                        "sourceReferenceImages": [],
                        "sourceVideos": [],
                        "contentHash": content_hash(block),
                        "importedAt": imported_at,
                        "sourceFile": str(md_path.relative_to(repo)).replace("\\", "/"),
                        "sourceOrdinal": ordinal,
                    }
                )
    count = write_jsonl(SOURCES / "zerolu" / "prompts.jsonl", rows)
    update_manifest("zerolu", commit=commit, count=count, imported_at=imported_at)
    return count


def ensure_forge_original_manifest() -> None:
    path = SOURCES / "forge-original" / "prompts.csv"
    count = 0
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        for _ in csv.DictReader(f):
            count += 1
    data_path = SOURCES / "forge-original" / "manifest.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    data["record_count"] = count
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import YouMind and ZeroLu into decoupled seedance-forge sources.")
    parser.add_argument("--source-root", required=True, help="Directory containing cloned source repositories.")
    parser.add_argument("--youmind-dir", default="awesome-seedance-2-prompts")
    parser.add_argument("--zerolu-dir", default="awesome-seedance")
    args = parser.parse_args()

    source_root = Path(args.source_root)
    imported_at = now_iso()
    ensure_forge_original_manifest()
    counts = {
        "youmind": import_youmind(source_root / args.youmind_dir, imported_at),
        "zerolu": import_zerolu(source_root / args.zerolu_dir, imported_at),
    }
    print(json.dumps({"imported_at": imported_at, "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
