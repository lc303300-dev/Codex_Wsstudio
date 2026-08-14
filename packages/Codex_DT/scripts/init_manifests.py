#!/usr/bin/env python3
"""Create draft manifests from previews/_previews.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_paths import existing_runtime_path
from model_policy import DEFAULT_MODEL, build_model_selection, normalize_model, validate_settings

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "image-manifest.template.json"
SUPPORTED_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
RATIO_VALUES = {
    "21:9": 21 / 9,
    "16:9": 16 / 9,
    "4:3": 4 / 3,
    "1:1": 1,
    "3:4": 3 / 4,
    "9:16": 9 / 16,
}


def workspace_rel(path_value: str) -> str:
    path = Path(path_value)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def image_id(index: int, source_image: str) -> str:
    stem = Path(source_image).stem
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in stem).strip("._-")
    if not safe:
        safe = f"image-{index:03d}"
    return f"{index:03d}-{safe}"


def nearest_ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive to infer ratio.")
    actual = width / height
    return min(SUPPORTED_RATIOS, key=lambda ratio: abs(RATIO_VALUES[ratio] - actual))


def validate_preview_record(record: dict[str, Any]) -> None:
    required = ("input_path", "preview_path", "preview_width", "preview_height", "max_long_edge")
    missing = [key for key in required if key not in record]
    if missing:
        raise SystemExit(f"Preview record is missing required fields: {', '.join(missing)}")
    width = int(record["preview_width"])
    height = int(record["preview_height"])
    max_long_edge = int(record["max_long_edge"])
    if width < 1 or height < 1 or max(width, height) > 1024 or max_long_edge > 1024:
        raise SystemExit(f"Preview exceeds the 1024px inspection limit: {record['preview_path']}")
    if Path(record["input_path"]).resolve() == Path(record["preview_path"]).resolve():
        raise SystemExit("Preview path must not point to the original raster image.")
    metadata_path = Path(record["preview_path"]).with_suffix(".json")
    if not metadata_path.is_file():
        raise SystemExit(f"Preview metadata file is missing: {metadata_path}")


def build_manifest(template: dict[str, Any], index: int, record: dict[str, Any], duration: int, ratio: str | None, prompts: Path, model: str, model_selection: dict[str, Any]) -> dict[str, Any]:
    source = workspace_rel(str(record["input_path"]))
    preview = workspace_rel(str(record["preview_path"]))
    item_id = image_id(index, source)
    prompt_file = workspace_rel(str(prompts / f"{item_id}.prompt.txt"))
    manifest = json.loads(json.dumps(template, ensure_ascii=False))
    manifest["id"] = item_id
    manifest["source_image"] = source
    manifest["preview_image"] = preview
    manifest["photo_type"] = "待 Codex 识别"
    manifest["prompt"]["file"] = prompt_file
    manifest["prompt"]["status"] = "draft"
    manifest["mqrox_compile"]["duration"] = duration
    manifest["mqrox_compile"]["model_version"] = model
    manifest["mqrox_compile"]["model_selection"] = model_selection
    if ratio is None:
        ratio = nearest_ratio(int(record["original_width"]), int(record["original_height"]))
    manifest["mqrox_compile"]["ratio"] = ratio
    manifest["mqrox_compile"]["asset_manifest"]["duration"] = duration
    manifest["mqrox_compile"]["asset_manifest"]["ratio"] = ratio
    asset = manifest["mqrox_compile"]["asset_manifest"]["assets"][0]
    asset["source"] = source
    return manifest


def parse_brief(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--brief must use IMAGE_ID=TEXT, for example 001-image1=固定镜头")
    image_key, brief = value.split("=", 1)
    image_key = image_key.strip()
    brief = brief.strip()
    if not image_key or not brief:
        raise argparse.ArgumentTypeError("--brief requires both image id/key and text")
    return image_key, brief


def read_request(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    data = read_json(path)
    if not isinstance(data, dict):
        raise SystemExit(f"Expected an object in request metadata: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize draft manifests from preview records.")
    parser.add_argument("--previews", type=Path, default=ROOT / "previews" / "_previews.json")
    parser.add_argument("--manifests", type=Path, default=ROOT / "manifests")
    parser.add_argument("--prompts", type=Path, default=ROOT / "prompts")
    parser.add_argument("--batch", help="Batch/task id. Uses previews/<batch>, manifests/<batch>, and prompts/<batch>.")
    parser.add_argument("--duration", type=int, help="Required video duration in seconds; allowed range depends on the selected model. Defaults to private batch request metadata when present.")
    parser.add_argument("--ratio", help="Optional target ratio: 21:9, 16:9, 4:3, 1:1, 3:4, or 9:16. If omitted, the nearest image ratio is used.")
    parser.add_argument("--brief", action="append", type=parse_brief, default=[], help="Per-image user motion brief as IMAGE_ID=TEXT. Keys may be manifest ids like 001-image1, input stems like image1, or 1-based indexes.")
    parser.add_argument("--request", type=Path, help="Optional request metadata JSON. Defaults to .codex-image-private/batches/<batch>/request.json when available.")
    parser.add_argument("--model-version", help="Explicit user-selected video model. Defaults to request metadata, then Seedance 2.5.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing manifest files.")
    args = parser.parse_args()
    if args.batch:
        args.previews = ROOT / "previews" / args.batch / "_previews.json"
        args.manifests = ROOT / "manifests" / args.batch
        args.prompts = ROOT / "prompts" / args.batch
        if args.request is None:
            default_request = existing_runtime_path(
                args.batch,
                "request.json",
                legacy_parts=("outputs", args.batch, "request.json"),
            )
            if default_request.is_file():
                args.request = default_request

    request = read_request(args.request)
    duration = args.duration if args.duration is not None else request.get("duration")
    ratio = args.ratio if args.ratio is not None else request.get("ratio")
    request_brief = str(request.get("user_request_zh", "")).strip()
    request_model = request.get("model") if isinstance(request.get("model"), dict) else {}
    if args.model_version is not None:
        try:
            model = normalize_model(args.model_version)
            model_selection = build_model_selection(args.model_version, explicit=True, user_text=request_brief or None)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    elif request_model:
        try:
            model = normalize_model(request_model.get("requested"))
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        model_selection = dict(request_model)
        model_selection["requested"] = model
        if model.startswith("seedance2.0") and model_selection.get("selection_source") != "user_explicit":
            raise SystemExit("Seedance 2.0 request metadata must record selection_source=user_explicit.")
    else:
        model = DEFAULT_MODEL
        model_selection = build_model_selection(DEFAULT_MODEL, explicit=False)

    if duration is None:
        raise SystemExit("--duration is required unless private batch request metadata provides duration.")
    if not isinstance(duration, int):
        raise SystemExit("--duration must be an integer from 4 through 30 seconds.")
    if not 4 <= duration <= 30:
        raise SystemExit("--duration must be an integer from 4 through 30 seconds.")
    if ratio is not None and ratio not in SUPPORTED_RATIOS:
        raise SystemExit(f"--ratio must be one of: {', '.join(SUPPORTED_RATIOS)}.")

    records = read_json(args.previews)
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise SystemExit(f"Expected a list or object in {args.previews}")
    if not records:
        raise SystemExit(f"No preview records found in {args.previews}. Put images in inputs/<batch>/ and run prepare_previews.ps1 first.")
    template = read_json(TEMPLATE)
    created = 0
    skipped = 0
    brief_by_key = dict(args.brief)
    for index, record in enumerate(records, start=1):
        validate_preview_record(record)
        effective_ratio = ratio or nearest_ratio(int(record["original_width"]), int(record["original_height"]))
        try:
            validate_settings(model, duration, str(template["mqrox_compile"].get("resolution") or "480p"), effective_ratio)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        manifest = build_manifest(template, index, record, duration, effective_ratio, args.prompts, model, model_selection)
        source_stem = Path(manifest["source_image"]).stem
        brief = brief_by_key.get(manifest["id"]) or brief_by_key.get(source_stem) or brief_by_key.get(str(index)) or request_brief
        if brief:
            manifest.setdefault("user_requirements", {})["motion_zh"] = brief
        out = args.manifests / f"{manifest['id']}.json"
        if out.exists() and not args.force:
            skipped += 1
            continue
        write_json(out, manifest)
        created += 1
        print(f"{manifest['id']}: duration={manifest['mqrox_compile']['duration']} ratio={manifest['mqrox_compile']['ratio']}")
    print(f"Created {created} manifest(s), skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
