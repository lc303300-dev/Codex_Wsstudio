#!/usr/bin/env python3
"""Record that one image task was dispatched to a subagent."""

from __future__ import annotations

import argparse

from image_job_state import (
    dispatch_slots_available,
    find_image,
    locked_jobs,
    load_jobs,
    now_iso,
    resolve_workspace_path,
    sha256_file,
    update_run_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record one image subagent dispatch.")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--agent-nickname")
    parser.add_argument(
        "--force-agent-id",
        action="store_true",
        help="Replace an existing dispatch agent id. Use only when correcting a bad manual record.",
    )
    parser.add_argument("--lock-timeout", type=float, default=30, help="Seconds to wait for image_jobs.json lock.")
    args = parser.parse_args()

    with locked_jobs(args.batch, args.lock_timeout) as jobs:
        image = find_image(jobs, args.image_id)
        current_status = image.get("status")
        current_dispatch = image.get("dispatch") or {}
        current_agent_id = current_dispatch.get("agent_id")
        if current_status in {"dispatched", "recorded"} and current_agent_id == args.agent_id and not args.force_agent_id:
            print(f"{args.image_id} already {current_status} for agent {args.agent_id}; unchanged")
            return 0
        if current_status in {"dispatched", "recorded"} and current_agent_id and current_agent_id != args.agent_id and not args.force_agent_id:
            raise SystemExit(
                f"{args.image_id} already has dispatch agent {current_agent_id}; "
                "pass --force-agent-id only when correcting that record."
            )
        if current_status == "pending" and dispatch_slots_available(jobs) <= 0:
            raise SystemExit("No dispatch slots available. Wait for an active subagent or raise max_concurrent_images.")
        if current_status not in {"pending", "dispatched", "recorded"}:
            raise SystemExit(f"{args.image_id} has unsupported status for dispatch recording: {current_status}")

        task_file = resolve_workspace_path(image["task_file"])
        manifest_file = resolve_workspace_path(image["manifest"])
        if not task_file.is_file():
            raise SystemExit(f"Missing task file: {task_file}")
        if not manifest_file.is_file():
            raise SystemExit(f"Missing manifest: {manifest_file}")

        image["dispatch"] = {
            "agent_id": args.agent_id,
            "agent_nickname": args.agent_nickname,
            "task_file_sha256": sha256_file(task_file),
            "manifest_sha256_at_dispatch": sha256_file(manifest_file),
            "dispatched_at": current_dispatch.get("dispatched_at") or now_iso(),
        }
        if current_status == "pending":
            image["status"] = "dispatched"
        update_run_status(jobs)
    print(f"{args.image_id} -> dispatched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
