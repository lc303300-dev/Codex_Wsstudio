#!/usr/bin/env python3
"""Record that one dispatched image task produced reviewable outputs."""

from __future__ import annotations

import argparse
import json

from image_job_state import find_image, locked_jobs, now_iso, read_json, resolve_workspace_path, sha256_file, update_run_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Record one image subagent result after main-agent review.")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--allow-validator-warning", action="store_true")
    parser.add_argument(
        "--recover-missing-dispatch",
        action="store_true",
        help="Record a completed result even if dispatch was not recorded before the worker ran.",
    )
    parser.add_argument("--lock-timeout", type=float, default=30, help="Seconds to wait for image_jobs.json lock.")
    args = parser.parse_args()

    with locked_jobs(args.batch, args.lock_timeout) as jobs:
        image = find_image(jobs, args.image_id)
        image_status = image.get("status")
        dispatch = image.get("dispatch") or {}
        if image_status == "dispatched":
            if dispatch.get("agent_id") != args.agent_id:
                raise SystemExit(
                    f"Agent id mismatch for {args.image_id}: dispatch={dispatch.get('agent_id')} result={args.agent_id}"
                )
        elif image_status == "recorded":
            previous = image.get("result") or {}
            if previous.get("agent_id") != args.agent_id:
                raise SystemExit(
                    f"Agent id mismatch for recorded {args.image_id}: previous={previous.get('agent_id')} result={args.agent_id}"
                )
        elif image_status == "pending" and args.recover_missing_dispatch:
            task_file = resolve_workspace_path(image["task_file"])
            manifest_at_recovery = resolve_workspace_path(image["manifest"])
            if not task_file.is_file():
                raise SystemExit(f"Missing task file: {task_file}")
            dispatch = {
                "agent_id": args.agent_id,
                "agent_nickname": None,
                "task_file_sha256": sha256_file(task_file),
                "manifest_sha256_at_dispatch": sha256_file(manifest_at_recovery) if manifest_at_recovery.is_file() else None,
                "dispatched_at": now_iso(),
                "recovered": True,
                "recovery_note": "Dispatch was not recorded before the worker finished; recovered from reviewable outputs.",
            }
            image["dispatch"] = dispatch
        else:
            raise SystemExit(
                f"{args.image_id} must be dispatched before result recording; got {image_status}. "
                "Use --recover-missing-dispatch only when the worker already produced reviewable files."
            )

        manifest_file = resolve_workspace_path(image["manifest"])
        prompt_file = resolve_workspace_path(image["prompt_file"])
        if not manifest_file.is_file():
            raise SystemExit(f"Missing manifest: {manifest_file}")
        if not prompt_file.is_file() or not prompt_file.read_text(encoding="utf-8").strip():
            raise SystemExit(f"Missing or empty prompt file: {prompt_file}")

        manifest = read_json(manifest_file)
        status = manifest.get("prompt", {}).get("status")
        validator = manifest.get("mqrox_compile", {}).get("validator", {})
        if status != "ready_for_review":
            raise SystemExit(f"{args.image_id} prompt.status must be ready_for_review before recording; got {status!r}")
        if validator.get("ok") is not True and not args.allow_validator_warning:
            raise SystemExit(f"{args.image_id} validator ok is not true. Re-run validation or pass --allow-validator-warning.")

        previous_result = image.get("result") or {}
        image["result"] = {
            "agent_id": args.agent_id,
            "recorded_at": previous_result.get("recorded_at") or now_iso(),
            "manifest_sha256": sha256_file(manifest_file),
            "prompt_sha256": sha256_file(prompt_file),
            "prompt_status": status,
            "validator_ok": validator.get("ok"),
        }
        image["status"] = "recorded"
        update_run_status(jobs)
    print(json.dumps({"image_id": args.image_id, "status": "recorded", "validator_ok": validator.get("ok")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
