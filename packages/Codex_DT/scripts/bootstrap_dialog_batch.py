#!/usr/bin/env python3
"""Bootstrap a dialog-image batch without starting visual/subagent generation."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH_RE = re.compile(r"^batch=(?P<batch>\S+)$", re.MULTILINE)


def run_capture(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "First-turn bootstrap for multiple images dropped into Codex: import files, "
            "optionally prepare previews/manifests, then stop before visual work, subagents, or paid generation."
        )
    )
    parser.add_argument("--name", required=True, help="Descriptive suffix for YYYYMMDD-HHMM-<name>.")
    parser.add_argument("--images", nargs="+", type=Path, required=True, help="Image paths provided by Codex attachments.")
    parser.add_argument("--duration", type=int, help="Optional known duration in seconds, 4 through 15.")
    parser.add_argument("--ratio", help="Optional target ratio: 21:9, 16:9, 4:3, 1:1, 3:4, or 9:16.")
    parser.add_argument("--wait-timeout", type=float, default=120.0)
    parser.add_argument("--stable-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.duration is not None and not 4 <= args.duration <= 15:
        raise SystemExit("--duration must be an integer from 4 through 15 seconds.")
    supported_ratios = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}
    if args.ratio is not None and args.ratio not in supported_ratios:
        raise SystemExit(f"--ratio must be one of: {', '.join(sorted(supported_ratios))}.")

    import_command = [
        sys.executable,
        "scripts/import_dialog_images.py",
        "--name",
        args.name,
        "--wait-timeout",
        str(args.wait_timeout),
        "--stable-seconds",
        str(args.stable_seconds),
        "--images",
        *[str(path) for path in args.images],
    ]
    output = run_capture(import_command)
    match = BATCH_RE.search(output)
    if not match:
        raise SystemExit("Could not determine batch id from import output.")
    batch = match.group("batch")

    if args.duration is not None:
        run_capture(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts/prepare_previews.ps1",
                "-Batch",
                batch,
            ]
        )
        manifest_command = [
            sys.executable,
            "scripts/init_manifests.py",
            "--batch",
            batch,
            "--duration",
            str(args.duration),
        ]
        if args.ratio:
            manifest_command.extend(["--ratio", args.ratio])
        run_capture(manifest_command)

    print()
    print(f"bootstrap_batch={batch}")
    if args.duration is None:
        print(f"next: provide duration, then run previews/manifests for {batch}")
    else:
        print(f"next: continue generation from batch {batch}")
        print(f"command: python scripts/make_subagent_tasks.py --batch {batch} --status draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
