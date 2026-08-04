#!/usr/bin/env python3
"""Check subagent deliverables before building the user review page."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_paths import existing_runtime_path, runtime_path

ROOT = Path(__file__).resolve().parents[1]
STOPWORDS_ZH = {
    "人物",
    "之后",
    "然后",
    "画面",
    "进行",
    "保持",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_workspace_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def requirement_terms(text: str) -> list[str]:
    terms: list[str] = []
    current = []
    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            current.append(char)
        else:
            if len(current) >= 2:
                terms.append("".join(current))
            current = []
    if len(current) >= 2:
        terms.append("".join(current))

    keywords: list[str] = []
    for term in terms:
        if term in STOPWORDS_ZH:
            continue
        if len(term) <= 4:
            keywords.append(term)
        for size in (4, 2):
            if len(term) < size:
                continue
            for index in range(0, len(term) - size + 1):
                piece = term[index : index + size]
                if piece not in STOPWORDS_ZH:
                    keywords.append(piece)
    return sorted(set(keywords), key=len, reverse=True)


def manifest_summary(path: Path) -> dict[str, Any]:
    manifest = read_json(path)
    prompt_file = resolve_workspace_path(manifest.get("prompt", {}).get("file", ""))
    prompt_text = prompt_file.read_text(encoding="utf-8").strip() if prompt_file.is_file() else ""
    validator = manifest.get("mqrox_compile", {}).get("validator", {})
    forge_matches = manifest.get("forge", {}).get("matches", [])
    status = manifest.get("prompt", {}).get("status")
    issues: list[str] = []
    if status != "ready_for_review":
        issues.append(f"prompt.status is {status!r}, expected 'ready_for_review'")
    if not prompt_file.is_file():
        issues.append(f"prompt file missing: {prompt_file}")
    elif not prompt_text:
        issues.append(f"prompt file is empty: {prompt_file}")
    if validator.get("ok") is not True:
        issues.append("validator ok is not true")
    if not isinstance(forge_matches, list) or not forge_matches:
        issues.append("forge matches are missing")
    if not manifest.get("visual", {}).get("description_zh"):
        issues.append("visual.description_zh is empty")
    if not manifest.get("motion_plan", {}).get("camera_motion_zh"):
        issues.append("motion_plan.camera_motion_zh is empty")
    user_motion = manifest.get("user_requirements", {}).get("motion_zh", "").strip()
    if user_motion:
        terms = requirement_terms(user_motion)
        covered = [term for term in terms if term in prompt_text]
        if terms and len(covered) < max(1, min(3, len(terms))):
            issues.append(f"user motion brief may not be covered in prompt: {user_motion}")

    return {
        "id": manifest.get("id", path.stem),
        "manifest": path.relative_to(ROOT).as_posix(),
        "prompt_file": prompt_file.relative_to(ROOT).as_posix() if prompt_file.is_relative_to(ROOT) else prompt_file.as_posix(),
        "status": status,
        "validator_ok": validator.get("ok"),
        "forge_match_count": len(forge_matches) if isinstance(forge_matches, list) else 0,
        "prompt_chars": len(prompt_text),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review subagent output completeness for one batch.")
    parser.add_argument("--batch", required=True, help="Batch/task id.")
    parser.add_argument("--manifests", type=Path, help="Override manifest directory.")
    parser.add_argument("--out", type=Path, help="Review report path.")
    args = parser.parse_args()

    manifests_dir = args.manifests or ROOT / "manifests" / args.batch
    out = args.out or runtime_path(args.batch, "main-agent-review.json")
    manifest_paths = sorted(path for path in manifests_dir.glob("*.json") if path.is_file())
    task_dir = existing_runtime_path(
        args.batch,
        "subagent-tasks",
        legacy_parts=("outputs", args.batch, "logs", "subagent-tasks"),
    )
    task_count = len(list(task_dir.glob("*.task.txt"))) if task_dir.is_dir() else 0
    summaries = [manifest_summary(path) for path in manifest_paths]
    failures = sum(1 for item in summaries if item["issues"])
    report = {
        "batch": args.batch,
        "manifest_count": len(manifest_paths),
        "subagent_task_count": task_count,
        "all_ready": failures == 0 and len(manifest_paths) > 0,
        "items": summaries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Reviewed {len(manifest_paths)} manifest(s), failures: {failures}")
    print(f"Report: {out}")
    for item in summaries:
        status = "PASS" if not item["issues"] else "FAIL"
        print(f"{status} {item['id']}: status={item['status']} validator={item['validator_ok']} matches={item['forge_match_count']}")
        for issue in item["issues"]:
            print(f"  - {issue}")
    return 1 if failures or len(manifest_paths) == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
