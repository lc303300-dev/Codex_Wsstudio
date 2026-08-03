#!/usr/bin/env python3
"""Print the current pipeline state for this workspace."""

from __future__ import annotations

import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def count(base: Path, pattern: str) -> int:
    return len(list(base.glob(pattern)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Print pipeline state.")
    parser.add_argument("--batch", help="Batch/task id to inspect.")
    args = parser.parse_args()

    base = ROOT
    manifests_dir = ROOT / "manifests"
    if args.batch:
        manifests_dir = ROOT / "manifests" / args.batch

    manifests = sorted(manifests_dir.glob("*.json"))
    statuses: dict[str, int] = {}
    for path in manifests:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            status = data.get("prompt", {}).get("status", "unknown")
        except Exception:
            status = "invalid"
        statuses[status] = statuses.get(status, 0) + 1

    print("Codex_DT pipeline status")
    if args.batch:
        print(f"batch: {args.batch}")
    print(f"inputs: {count(base, f'inputs/{args.batch}/*') if args.batch else count(base, 'inputs/*')}")
    print(f"previews: {count(base, f'previews/{args.batch}/*.jpg') if args.batch else count(base, 'previews/*.jpg')}")
    print(f"manifests: {len(manifests)}")
    for status, value in sorted(statuses.items()):
        print(f"  {status}: {value}")
    print(f"prompts: {count(base, f'prompts/{args.batch}/*.txt') if args.batch else count(base, 'prompts/*.txt')}")
    print(f"videos: {count(base, f'outputs/{args.batch}/videos/**/*.mp4') if args.batch else count(base, 'outputs/videos/**/*.mp4')}")
    print("default entry: follow AGENTS.md, not direct global seedance-cli.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
