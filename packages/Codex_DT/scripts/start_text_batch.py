#!/usr/bin/env python3
"""Create an empty text-first batch and record the user's video request."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from runtime_paths import runtime_path

ROOT = Path(__file__).resolve().parents[1]
BATCH_RE = re.compile(r"^batch=(?P<batch>\S+)$", re.MULTILINE)
SUPPORTED_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")


def run_capture(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.stdout


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Text-first entrypoint: create an empty batch, create inputs/<batch>/ "
            "for user image drop-off, and save the request for later manifest initialization."
        )
    )
    parser.add_argument("--name", required=True, help="Descriptive suffix for YYYYMMDD-HHMM-<name>.")
    parser.add_argument("--duration", type=int, required=True, help="Required video duration in seconds, 4 through 15.")
    parser.add_argument("--ratio", help="Optional target ratio: 21:9, 16:9, 4:3, 1:1, 3:4, or 9:16.")
    parser.add_argument("--request", required=True, help="Original Chinese user request, including motion/camera constraints.")
    parser.add_argument("--auto-generate", action="store_true", help="Record that confirmation should be skipped after review finalization.")
    args = parser.parse_args()

    if not 4 <= args.duration <= 15:
        raise SystemExit("--duration must be an integer from 4 through 15 seconds.")
    if args.ratio is not None and args.ratio not in SUPPORTED_RATIOS:
        raise SystemExit(f"--ratio must be one of: {', '.join(SUPPORTED_RATIOS)}.")

    output = run_capture([sys.executable, "scripts/new_batch.py", "--name", args.name])
    match = BATCH_RE.search(output)
    if not match:
        raise SystemExit("Could not determine batch id from new_batch.py output.")
    batch = match.group("batch")

    input_dir = ROOT / "inputs" / batch
    request_file = runtime_path(batch, "request.json")
    write_json(
        request_file,
        {
            "batch": batch,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "duration": args.duration,
            "ratio": args.ratio,
            "user_request_zh": args.request,
            "auto_generate": bool(args.auto_generate),
            "image_drop_dir": str(input_dir),
        },
    )

    print()
    print(f"text_batch={batch}")
    print(f"image_drop_dir={input_dir}")
    print(f"request_file={request_file}")
    print("next_after_images:")
    print(f"  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch {batch}")
    init_command = f"  python scripts/init_manifests.py --batch {batch}"
    if args.ratio:
        init_command += f" --ratio {args.ratio}"
    print(init_command)
    print(f"  python scripts/make_subagent_tasks.py --batch {batch} --status draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
