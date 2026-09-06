#!/usr/bin/env python3
"""Apply the environment-motion compiler to one or more manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from environment_motion import apply_to_manifest


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile detected plant/water motion into manifests.")
    parser.add_argument("--manifest", type=Path, action="append", help="Manifest JSON; repeatable.")
    parser.add_argument("--manifests", type=Path, help="Directory containing manifest JSON files.")
    parser.add_argument("--batch", help="Use manifests/<batch>.")
    parser.add_argument("--intensity", choices=("subtle", "moderate"), default="subtle")
    args = parser.parse_args()

    paths = list(args.manifest or [])
    if args.batch:
        root = Path(__file__).resolve().parents[1]
        args.manifests = root / "manifests" / args.batch
    if args.manifests:
        paths.extend(sorted(args.manifests.glob("*.json")))
    paths = list(dict.fromkeys(path.resolve() for path in paths if path.is_file()))
    if not paths:
        raise SystemExit("Provide --manifest, --manifests, or --batch with at least one JSON manifest.")

    for path in paths:
        manifest = apply_to_manifest(read_json(path), intensity=args.intensity)
        write_json(path, manifest)
        elements = ", ".join(item["label_zh"] for item in manifest["environment_motion"]["elements"]) or "无匹配环境元素"
        print(f"{path.name}: {elements}")
    print(f"Compiled {len(paths)} manifest(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

