#!/usr/bin/env python3
"""Validate all pipeline prompts with mqrox validate_prompt.py."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_paths import PRIVATE_RUNTIME_ROOT, runtime_path
from model_policy import validate_manifest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "third_party" / "seedance-2.0-prompt-skill" / "build-seedance2-prompts" / "scripts" / "validate_prompt.py"
SUPPORTED_RATIOS = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_workspace_path(path_value: str) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def run_validator(prompt_file: Path, asset_manifest_file: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(VALIDATOR),
        str(prompt_file),
        "--manifest",
        str(asset_manifest_file),
        "--format",
        "json",
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
    if result.stdout.strip():
        payload = json.loads(result.stdout)
    else:
        payload = {
            "ok": False,
            "issues": [
                {
                    "severity": "error",
                    "code": "PIPELINE",
                    "message": result.stderr.strip() or "Validator produced no output.",
                    "basis": "pipeline",
                }
            ],
        }
    payload["returncode"] = result.returncode
    if result.stderr.strip():
        payload["stderr"] = result.stderr.strip()
    return payload


def validate_cli_prompt(prompt_text: str, asset_manifest: dict[str, Any], duration: int, ratio: str) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not prompt_text.strip():
        issues.append({
            "severity": "error",
            "code": "PIPELINE",
            "message": "Prompt is empty.",
            "basis": "pipeline",
        })
    if re.search(r"@(图片|Image|视频|Video|音频|Audio)\s*\d+", prompt_text):
        issues.append({
            "severity": "error",
            "code": "CLI_BINDING",
            "message": "Dreamina CLI binding comes from ordered multimodal2video arguments; do not type Web UI mention labels such as @Image 1, @图片1, @Video 1, or @视频1 in CLI prompts.",
            "basis": "Codex_image",
        })
    if "图片1" not in prompt_text:
        issues.append({
            "severity": "error",
            "code": "CLI_BINDING",
            "message": "Dreamina CLI prompt should refer to the first ordered --image upload as 图片1.",
            "basis": "pipeline",
        })

    assets = asset_manifest.get("assets", [])
    image_assets = [asset for asset in assets if isinstance(asset, dict) and asset.get("modality") == "image"]
    if not image_assets:
        issues.append({
            "severity": "error",
            "code": "ASSET_MANIFEST",
            "message": "Dreamina CLI multimodal2video expects at least one ordered source image in this pipeline.",
            "basis": "pipeline",
        })
    elif image_assets[0].get("index") != 1 or image_assets[0].get("tag") != "图片1":
        issues.append({
            "severity": "error",
            "code": "ASSET_MANIFEST",
            "message": "The first image asset must be tagged 图片1 and match the first --image upload.",
            "basis": "pipeline",
        })
    elif re.search(r"@(图片|Image|视频|Video|音频|Audio)\s*\d+", str(image_assets[0].get("tag", ""))):
        issues.append({
            "severity": "error",
            "code": "ASSET_MANIFEST",
            "message": "Dreamina CLI asset manifest tag must not store a Web UI mention label; use bare labels such as 图片1.",
            "basis": "pipeline",
        })

    if asset_manifest.get("duration") != duration:
        issues.append({
            "severity": "error",
            "code": "ASSET_MANIFEST",
            "message": "Asset manifest duration does not match mqrox_compile.duration.",
            "basis": "pipeline",
        })
    if asset_manifest.get("ratio") != ratio:
        issues.append({
            "severity": "error",
            "code": "ASSET_MANIFEST",
            "message": "Asset manifest ratio does not match mqrox_compile.ratio.",
            "basis": "pipeline",
        })
    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
        "returncode": 1 if any(issue["severity"] == "error" for issue in issues) else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate all manifests and prompt files.")
    parser.add_argument("--manifests", type=Path, default=ROOT / "manifests")
    parser.add_argument("--tmp", type=Path, default=PRIVATE_RUNTIME_ROOT / "asset-manifests")
    parser.add_argument("--batch", help="Batch/task id. Uses manifests/<batch> and private temporary asset manifests.")
    args = parser.parse_args()
    if args.batch:
        args.manifests = ROOT / "manifests" / args.batch
        args.tmp = runtime_path(args.batch, "asset-manifests")

    args.tmp.mkdir(parents=True, exist_ok=True)
    if args.manifests.is_file():
        manifest_paths = [args.manifests]
    else:
        manifest_paths = sorted(path for path in args.manifests.glob("*.json") if path.is_file())
    failures = 0
    for manifest_path in manifest_paths:
        manifest = read_json(manifest_path)
        prompt_file = resolve_workspace_path(manifest.get("prompt", {}).get("file", ""))
        asset_manifest = manifest.get("mqrox_compile", {}).get("asset_manifest", {})
        duration = manifest.get("mqrox_compile", {}).get("duration")
        ratio = manifest.get("mqrox_compile", {}).get("ratio")
        preflight_issues = []
        try:
            validate_manifest(manifest)
        except ValueError as exc:
            preflight_issues.append({
                "severity": "error",
                "code": "MODEL_POLICY",
                "message": str(exc),
                "basis": "pipeline",
            })
        if duration is None:
            preflight_issues.append({
                "severity": "error",
                "code": "PIPELINE",
                "message": "Duration is required before validation/generation.",
                "basis": "pipeline",
            })
        if ratio is None or ratio == "":
            preflight_issues.append({
                "severity": "error",
                "code": "PIPELINE",
                "message": "Ratio is required before validation/generation.",
                "basis": "pipeline",
            })
        elif ratio not in SUPPORTED_RATIOS:
            preflight_issues.append({
                "severity": "error",
                "code": "PIPELINE",
                "message": f"Unsupported ratio: {ratio}",
                "basis": "pipeline",
            })
        if preflight_issues:
            validation = {
                "ok": False,
                "issues": preflight_issues,
            }
            manifest.setdefault("mqrox_compile", {})["validator"] = {
                "ok": False,
                "issues": validation["issues"],
                "returncode": None,
            }
            write_json(manifest_path, manifest)
            print(f"FAIL {manifest_path.name}")
            failures += 1
            continue
        asset_manifest_file = args.tmp / f"{manifest_path.stem}.asset-manifest.json"
        write_json(asset_manifest_file, asset_manifest)

        if prompt_file is None or not prompt_file.is_file():
            validation = {
                "ok": False,
                "issues": [
                    {
                        "severity": "error",
                        "code": "PIPELINE",
                        "message": f"Prompt file not found: {prompt_file or '(empty prompt.file)'}",
                        "basis": "pipeline",
                    }
                ],
            }
        else:
            surface = manifest.get("mqrox_compile", {}).get("surface")
            if surface == "dreamina-cli":
                validation = validate_cli_prompt(prompt_file.read_text(encoding="utf-8"), asset_manifest, duration, ratio)
            else:
                validation = run_validator(prompt_file, asset_manifest_file)

        manifest.setdefault("mqrox_compile", {})["validator"] = {
            "ok": bool(validation.get("ok")),
            "issues": validation.get("issues", []),
            "returncode": validation.get("returncode"),
        }
        write_json(manifest_path, manifest)
        status = "PASS" if validation.get("ok") else "FAIL"
        print(f"{status} {manifest_path.name}")
        if not validation.get("ok"):
            failures += 1

    print(f"Validated {len(manifest_paths)} manifest(s), failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
