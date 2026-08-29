#!/usr/bin/env python3
"""Build the user review page for one batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from image_job_state import load_jobs

ROOT = Path(__file__).resolve().parents[1]


def run_step(command: list[str]) -> None:
    print(f"\n$ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def confirm_reviewable_manifests(batch: str) -> int:
    manifests_dir = ROOT / "manifests" / batch
    manifest_paths = sorted(path for path in manifests_dir.glob("*.json") if path.is_file())
    confirmed = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    for path in manifest_paths:
        manifest = read_json(path)
        prompt = manifest.setdefault("prompt", {})
        if prompt.get("status") != "ready_for_review":
            continue
        prompt_file = Path(prompt.get("file", ""))
        if not prompt_file.is_absolute():
            prompt_file = ROOT / prompt_file
        if not prompt_file.is_file() or not prompt_file.read_text(encoding="utf-8").strip():
            raise SystemExit(f"Cannot auto-confirm {path.name}: missing or empty prompt file.")
        prompt_text = prompt_file.read_text(encoding="utf-8").strip()
        prompt["status"] = "confirmed"
        prompt["confirmed_at"] = now
        prompt["confirmation_mode"] = "auto_generate"
        prompt["confirmed_sha256"] = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        write_json(path, manifest)
        confirmed += 1
    if confirmed == 0:
        raise SystemExit(f"No ready_for_review manifest found for auto generation in batch: {batch}")
    print(f"Auto-confirmed {confirmed} manifest(s).")
    return confirmed


def parse_agent_map(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit("--agent-map entries must use IMAGE_ID=AGENT_ID")
        image_id, agent_id = value.split("=", 1)
        image_id = image_id.strip()
        agent_id = agent_id.strip()
        if not image_id or not agent_id:
            raise SystemExit("--agent-map entries require both IMAGE_ID and AGENT_ID")
        result[image_id] = agent_id
    return result


def load_agent_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise SystemExit("--agent-map-file must contain a JSON object of image id to agent id")
    return {str(key): str(value) for key, value in payload.items()}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the user review page from subagent-written manifests and prompts."
    )
    parser.add_argument("--batch", required=True, help="Batch/task id.")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Optional diagnostic: run validate_batch.py before building the review page.",
    )
    parser.add_argument(
        "--check-subagent-outputs",
        action="store_true",
        help="Optional diagnostic: run review_subagent_outputs.py before building the review page.",
    )
    parser.add_argument(
        "--record-results",
        action="store_true",
        help="Optional bookkeeping: record each subagent result in image_jobs.json.",
    )
    parser.add_argument(
        "--auto-generate",
        action="store_true",
        help="Build review, auto-confirm ready prompts, then submit to Dreamina CLI without waiting for user review.",
    )
    parser.add_argument(
        "--allow-validator-warning",
        action="store_true",
        help="Pass through to record_image_result.py when --record-results is used.",
    )
    parser.add_argument(
        "--agent-map",
        action="append",
        default=[],
        metavar="IMAGE_ID=AGENT_ID",
        help="Recover missing dispatch records while finalizing. Can be repeated.",
    )
    parser.add_argument(
        "--agent-map-file",
        type=Path,
        help="JSON object mapping image ids to Codex agent ids for dispatch recovery.",
    )
    args = parser.parse_args()
    if args.validate:
        run_step([sys.executable, "scripts/validate_batch.py", "--batch", args.batch])
    if args.check_subagent_outputs:
        run_step([sys.executable, "scripts/review_subagent_outputs.py", "--batch", args.batch])

    if args.record_results:
        agent_map = load_agent_map(args.agent_map_file)
        agent_map.update(parse_agent_map(args.agent_map))
        jobs = load_jobs(args.batch)
        images = jobs.get("images", [])
        if not images:
            raise SystemExit(f"No image jobs found for batch: {args.batch}")

        for image in images:
            image_id = image.get("id")
            if not image_id:
                raise SystemExit("Image job is missing id.")
            dispatch = image.get("dispatch") or {}
            agent_id = dispatch.get("agent_id") or agent_map.get(str(image_id))
            if not agent_id:
                raise SystemExit(
                    f"{image_id} has no dispatch.agent_id; provide --agent-map {image_id}=<agent-id> "
                    "to recover a worker that finished before dispatch was recorded."
                )
            command = [
                sys.executable,
                "scripts/record_image_result.py",
                "--batch",
                args.batch,
                "--image-id",
                str(image_id),
                "--agent-id",
                str(agent_id),
            ]
            if not dispatch.get("agent_id"):
                command.append("--recover-missing-dispatch")
            if args.allow_validator_warning:
                command.append("--allow-validator-warning")
            run_step(command)

    run_step([sys.executable, "scripts/build_review.py", "--batch", args.batch])
    run_step([sys.executable, "scripts/pipeline_status.py", "--batch", args.batch])
    print(f"\nReview page: {ROOT / 'review' / args.batch / 'index.html'}")
    if args.auto_generate:
        confirm_reviewable_manifests(args.batch)
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/run_seedance_batch.ps1",
            "-Batch",
            args.batch,
            "-Yes",
        ]
        run_step(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
