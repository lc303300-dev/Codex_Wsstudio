from __future__ import annotations

import argparse
import json
import sys
from media_router.service import execute


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Unified Codex image and video router")
    commands = root.add_subparsers(dest="command", required=True)
    image = commands.add_parser("generate_image")
    image.add_argument("--prompt", required=True)
    image.add_argument("--image", action="append", default=[])
    video = commands.add_parser("generate_video")
    video.add_argument("--prompt", required=True)
    video.add_argument("--image", action="append", default=[])
    video.add_argument("--video", action="append", default=[])
    video.add_argument("--audio", action="append", default=[])
    return root


def main() -> int:
    args = parser().parse_args()
    result = execute(args.command, args.prompt, args.image, getattr(args, "video", ()), getattr(args, "audio", ()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    sys.exit(main())
