#!/usr/bin/env python3
"""Import images supplied from the Codex dialog into a stable pipeline batch."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from path_utils import normalize_windows_path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy one or more dialog-provided image paths into inputs/<batch>/ after "
            "waiting for each attachment file to become readable and size-stable."
        )
    )
    parser.add_argument("--name", required=True, help="Descriptive suffix for YYYYMMDD-HHMM-<name>.")
    parser.add_argument("--images", nargs="+", required=True, help="Image paths provided by Codex attachments.")
    parser.add_argument("--wait-timeout", type=float, default=120.0, help="Seconds to wait for each image. Default: 120.")
    parser.add_argument("--stable-seconds", type=float, default=2.0, help="Required stable file-size window. Default: 2.")
    parser.add_argument("--force", action="store_true", help="Allow overwriting existing copied image names.")
    args = parser.parse_args()

    command = [
        sys.executable,
        str(ROOT / "scripts" / "new_batch.py"),
        "--name",
        args.name,
        "--wait-timeout",
        str(args.wait_timeout),
        "--stable-seconds",
        str(args.stable_seconds),
        "--images",
        *[str(normalize_windows_path(path)) for path in args.images],
    ]
    if args.force:
        command.append("--force")

    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
