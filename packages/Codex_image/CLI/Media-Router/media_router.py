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
    image.add_argument("--image-resolution", choices=("1K", "2K", "4K"))
    image.add_argument("--image-provider", choices=("comfly-gemini-lite", "comfly-gpt-image-2", "dreamina-image"))
    video = commands.add_parser("generate_video")
    video.add_argument("--prompt", required=True)
    video.add_argument("--image", action="append", default=[])
    video.add_argument("--video", action="append", default=[])
    video.add_argument("--audio", action="append", default=[])
    video.add_argument("--video-duration", help="Seconds; accepts 5, 5s, or 5秒 and normalizes before CLI submission")
    video.add_argument("--video-ratio")
    video.add_argument("--video-model")
    video.add_argument("--video-model-selection-source", choices=("user_explicit",))
    video.add_argument("--video-execution-mode", choices=("production", "production_submit_only", "test_submit_only"), default="production")
    video.add_argument("--video-resolution")
    video.add_argument("--video-confirmation-model")
    video.add_argument("--video-confirmation-resolution")
    video.add_argument("--video-confirmation-duration", help="Confirmed seconds; accepts the same forms as --video-duration")
    video.add_argument("--video-count", type=int, choices=range(1, 11), default=1)
    video.add_argument("--video-group")
    return root


def main() -> int:
    args = parser().parse_args()
    options = {}
    if args.command == "generate_image":
        options = {"image_ratio": args.image_ratio, "image_provider": args.image_provider}
        if args.image_resolution is not None:
            options["image_resolution"] = args.image_resolution
    elif args.command == "generate_video":
        options = {
            "video_duration": args.video_duration,
            "video_ratio": args.video_ratio,
            "video_model": args.video_model,
            "video_model_selection_source": args.video_model_selection_source,
            "video_execution_mode": args.video_execution_mode,
            "video_resolution": args.video_resolution,
            "video_confirmation_model": args.video_confirmation_model,
            "video_confirmation_resolution": args.video_confirmation_resolution,
            "video_confirmation_duration": args.video_confirmation_duration,
            "video_count": args.video_count,
            "video_group": args.video_group,
        }
    result = execute(args.command, args.prompt, args.image, getattr(args, "video", ()), getattr(args, "audio", ()), **options)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"success", "submitted"} else 2


if __name__ == "__main__":
    sys.exit(main())
