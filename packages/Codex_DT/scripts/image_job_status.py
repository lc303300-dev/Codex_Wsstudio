#!/usr/bin/env python3
"""Print image subagent job status without modifying state."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict

from image_job_state import active_images, dispatch_slots_available, dispatchable_images, load_jobs, max_concurrent_images


def main() -> int:
    parser = argparse.ArgumentParser(description="Print image subagent job status.")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    jobs = load_jobs(args.batch)
    by_status: dict[str, list[str]] = defaultdict(list)
    for image in jobs.get("images", []):
        by_status[image.get("status", "unknown")].append(image.get("id", "unknown"))
    summary = {
        "batch": args.batch,
        "run_status": jobs.get("run_status"),
        "image_count": len(jobs.get("images", [])),
        "max_concurrent_images": max_concurrent_images(jobs),
        "active_dispatches": [image.get("id") for image in active_images(jobs)],
        "dispatch_slots_available": dispatch_slots_available(jobs),
        "dispatchable_images": [image.get("id") for image in dispatchable_images(jobs)],
        "counts": dict(Counter(image.get("status", "unknown") for image in jobs.get("images", []))),
        "images": dict(sorted(by_status.items())),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(f"batch={summary['batch']}")
    print(f"run_status={summary['run_status']}")
    print(f"max_concurrent_images={summary['max_concurrent_images']}")
    print(f"active_dispatches={', '.join(summary['active_dispatches']) if summary['active_dispatches'] else '-'}")
    print(f"dispatch_slots_available={summary['dispatch_slots_available']}")
    print(f"dispatchable_images={', '.join(summary['dispatchable_images']) if summary['dispatchable_images'] else '-'}")
    for status, image_ids in summary["images"].items():
        print(f"{status}: {', '.join(image_ids) if image_ids else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
