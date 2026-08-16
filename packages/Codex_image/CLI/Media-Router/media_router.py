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
    image.add_argument("--image-ratio", required=True, choices=("21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"))
    image.add_argument("--image-provider", choices=("comfly-gemini-lite", "comfly-gpt-image-2-all", "comfly-gpt-image-2", "apimart-gpt-image-2", "google-gemini-image", "dreamina-image"))
    video = commands.add_parser("generate_video")
    video.add_argument("--prompt", required=True)
    video.add_argument("--image", action="append", default=[])
    video.add_argument("--video", action="append", default=[])
    video.add_argument("--audio", action="append", default=[])
    video.add_argument("--video-duration")
    video.add_argument("--video-ratio")
    video.add_argument("--video-model")
    video.add_argument("--video-model-selection-source", choices=("user_explicit",))
    video.add_argument("--video-execution-mode", choices=("production", "production_submit_only", "test_submit_only"), default="production")
    video.add_argument("--video-resolution")
    return root


def main() -> int:
    args = parser().parse_args()
    options = {}
    if args.command == "generate_image":
        options = {"image_ratio": args.image_ratio, "image_provider": args.image_provider}
    elif args.command == "generate_video":
        options = {
            "video_duration": args.video_duration,
            "video_ratio": args.video_ratio,
            "video_model": args.video_model,
            "video_model_selection_source": args.video_model_selection_source,
            "video_execution_mode": args.video_execution_mode,
            "video_resolution": args.video_resolution,
        }
    result = execute(args.command, args.prompt, args.image, getattr(args, "video", ()), getattr(args, "audio", ()), **options)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"success", "submitted"} else 2


if __name__ == "__main__":
    sys.exit(main())
