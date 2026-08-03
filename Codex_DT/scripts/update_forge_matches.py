#!/usr/bin/env python3
"""Search seedance-forge for each manifest and write matches back."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / "scripts" / "search_forge.py"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def infer_patterns(match: dict[str, Any]) -> list[str]:
    text = " ".join(
        str(match.get(key, ""))
        for key in ("title", "description", "content_preview")
    ).lower()
    patterns: list[str] = []
    checks = [
        ("slow", "慢速运动/慢推节奏"),
        ("tracking", "跟拍或平移镜头"),
        ("push", "向前推进镜头"),
        ("pull back", "后拉揭示空间"),
        ("wide shot", "广角空镜/建立镜头"),
        ("close-up", "局部特写"),
        ("handheld", "轻微手持真实感"),
        ("sunlight", "自然光影变化"),
        ("rain", "天气或环境粒子动效"),
        ("wind", "风带动物体微动"),
        ("cinematic", "电影感构图与光线"),
        ("no subtitles", "禁止字幕"),
    ]
    for needle, label in checks:
        if needle in text and label not in patterns:
            patterns.append(label)
    return patterns[:6]


def search_manifest(path: Path, top: int, include_content: bool) -> dict[str, Any]:
    command = [
        sys.executable,
        str(SEARCH),
        "--manifest",
        str(path),
        "--top",
        str(top),
        "--preview-chars",
        "900",
    ]
    if include_content:
        command.append("--include-content")
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", capture_output=True, check=True)
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update all manifests with seedance-forge matches.")
    parser.add_argument("--manifests", type=Path, default=ROOT / "manifests")
    parser.add_argument("--batch", help="Batch/task id. Uses manifests/<batch>.")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--include-content", action="store_true")
    args = parser.parse_args()
    if args.batch:
        args.manifests = ROOT / "manifests" / args.batch

    if args.manifests.is_file():
        paths = [args.manifests]
    else:
        paths = sorted(path for path in args.manifests.glob("*.json") if path.is_file())
    updated = 0
    for path in paths:
        manifest = read_json(path)
        payload = search_manifest(path, args.top, args.include_content)
        matches = payload.get("matches", [])
        for match in matches:
            match["extracted_patterns"] = infer_patterns(match)
            if not args.include_content:
                match.pop("content", None)
        manifest.setdefault("forge", {})["last_query"] = payload.get("query", "")
        manifest["forge"]["matches"] = matches
        write_json(path, manifest)
        print(f"Updated {path.name}: {len(matches)} match(es)")
        updated += 1
    print(f"Updated {updated} manifest(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
