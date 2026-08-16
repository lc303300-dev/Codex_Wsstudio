from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "CLI" / "Media-Router"))

from media_router.providers import comfly_common  # noqa: E402
from media_router.config import load_config  # noqa: E402
from media_router.safe_logging import write_json  # noqa: E402


PROVIDER_CONFIG = load_config()["providers"]
MODEL_PROFILES = {}
for name, value in PROVIDER_CONFIG.items():
    if not name.startswith("comfly-"):
        continue
    MODEL_PROFILES[value["model"]] = value.get("size_profile")
    for model in value.get("models_by_resolution", {}).values():
        MODEL_PROFILES[model] = value.get("size_profile")
MODELS = tuple(MODEL_PROFILES)


def prompt_summary(prompt: str) -> dict:
    return {"value": "<redacted>", "characters": len(prompt), "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}


def read_prompt(args: argparse.Namespace) -> str:
    prompt = args.prompt if args.prompt is not None else Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("Prompt must not be empty")
    return prompt.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit single-model Comfly adapter diagnostic")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file")
    parser.add_argument("--model", required=True, choices=MODELS)
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--out", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--size")
    parser.add_argument("--resolution", choices=("1K", "2K", "4K"), default="1K")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prompt = read_prompt(args)
    images = tuple(Path(value).resolve() for value in args.image)
    missing = [str(path) for path in images if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing reference images: " + "; ".join(missing))
    output, log_path = Path(args.out).resolve(), Path(args.log).resolve()
    report = {
        "provider": "Comfly OpenAI-compatible image API",
        "model": args.model,
        "operation": "edit" if images else "generation",
        "endpoint": comfly_common.EDITS_URL if images else comfly_common.GENERATIONS_URL,
        "prompt": prompt_summary(prompt),
        "image_count": len(images),
        "size": comfly_common.normalize_size(args.model, args.size, MODEL_PROFILES[args.model], args.resolution),
        "dry_run": args.dry_run,
        "api_key_configured": bool(comfly_common.api_key()),
    }
    if args.dry_run:
        write_json(log_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    try:
        details = comfly_common.execute_once(args.model, prompt, images, output, args.size, args.timeout, size_profile=MODEL_PROFILES[args.model], resolution=args.resolution)
    except Exception as exc:
        report.update(status="failed", failure_type=type(exc).__name__)
        write_json(log_path, report)
        raise
    report.update(status="success", request_id=details.get("request_id"), output=str(output), output_bytes=details["output_bytes"])
    write_json(log_path, report)
    print(str(output))


if __name__ == "__main__":
    main()
