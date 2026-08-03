#!/usr/bin/env python3
"""Print the next subagent dispatch wave for one batch."""

from __future__ import annotations

import argparse
import json

from image_job_state import dispatch_slots_available, dispatchable_images, load_jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Show dispatchable image jobs and task files for the next subagent wave.")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    jobs = load_jobs(args.batch)
    slots = dispatch_slots_available(jobs)
    images = dispatchable_images(jobs)[:slots]
    plan = {
        "batch": args.batch,
        "dispatch_slots_available": slots,
        "wave_count": len(images),
        "items": [
            {
                "id": image.get("id"),
                "task_file": image.get("task_file"),
                "record_dispatch_command": (
                    f"python scripts/record_image_dispatch.py --batch {args.batch} "
                    f"--image-id {image.get('id')} --agent-id <agent-id>"
                ),
            }
            for image in images
        ],
    }
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    print(f"batch={args.batch}")
    print(f"dispatch_slots_available={slots}")
    print(f"wave_count={len(images)}")
    if not images:
        print("No dispatchable image jobs.")
        return 0
    for image in plan["items"]:
        print(f"\n{image['id']}")
        print(f"task_file={image['task_file']}")
        print(image["record_dispatch_command"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
