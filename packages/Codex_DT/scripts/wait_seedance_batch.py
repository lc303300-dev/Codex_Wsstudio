#!/usr/bin/env python3
"""Poll Dreamina async tasks for one batch until videos are downloaded."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from runtime_paths import existing_runtime_path, runtime_path

ROOT = Path(__file__).resolve().parents[1]


def configured_seedance_cli() -> Path | None:
    for name in ("SEEDANCE_CLI", "SEEDANCE_CLI_PATH", "DREAMINA_CLI"):
        value = os.environ.get(name)
        if value:
            return Path(value)
    for path in (ROOT / "config" / "pipeline.local.json", ROOT / "config" / "pipeline.json"):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        value = data.get("paths", {}).get("seedance_cli")
        if value:
            return Path(value)
    return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise SystemExit(f"Missing task log: {path}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSONL in {path} line {line_number}: {exc}") from exc
        if record.get("submit_id"):
            records.append(record)
    if not records:
        raise SystemExit(f"No submitted tasks with submit_id found in: {path}")
    return records


def extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {"raw_output": text}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"raw_output": text}
    return payload if isinstance(payload, dict) else {"payload": payload}


def run_query(seedance_cli: Path, submit_id: str, videos_dir: Path) -> tuple[int, str, dict[str, Any]]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(seedance_cli),
        "query_result",
        f"--submit_id={submit_id}",
        f"--download_dir={videos_dir}",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = result.stdout or ""
    return result.returncode, output, extract_json(output)


def current_mp4s(videos_dir: Path) -> list[Path]:
    return sorted(path.resolve() for path in videos_dir.rglob("*.mp4") if path.is_file())


def matching_downloads(videos_dir: Path, submit_id: str, known: set[Path]) -> list[Path]:
    matches = [path for path in current_mp4s(videos_dir) if submit_id in path.name]
    if matches:
        return matches
    return sorted(path for path in current_mp4s(videos_dir) if path not in known)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_manifest(batch: str, image_id: str, status: str, submit_id: str, files: list[Path], error: str | None) -> None:
    manifest_path = ROOT / "manifests" / batch / f"{image_id}.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    generation = manifest.setdefault("generation", {})
    generation["status"] = status
    generation["submit_id"] = submit_id
    generation["downloaded_files"] = [str(path) for path in files]
    generation["error"] = error
    write_json(manifest_path, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait until submitted Dreamina tasks download videos for a batch.")
    parser.add_argument("--batch", required=True, help="Batch/task id.")
    parser.add_argument("--seedance-cli", type=Path, default=None)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=0,
        help="0 means poll indefinitely until every submitted task has a downloaded mp4 or one task fails.",
    )
    args = parser.parse_args()

    if args.poll_seconds < 5:
        raise SystemExit("--poll-seconds must be at least 5.")
    seedance_cli = args.seedance_cli or configured_seedance_cli()
    if seedance_cli is None:
        raise SystemExit("Seedance CLI wrapper is not configured. Run scripts/deploy_project.ps1 first.")
    if not seedance_cli.is_file():
        raise SystemExit(f"Seedance CLI wrapper not found: {seedance_cli}")

    outputs_dir = ROOT / "outputs" / args.batch
    videos_dir = outputs_dir / "videos"
    logs_dir = runtime_path(args.batch, "dreamina-logs")
    videos_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    tasks_file = existing_runtime_path(
        args.batch,
        "tasks.jsonl",
        legacy_parts=("outputs", args.batch, "tasks.jsonl"),
    )
    tasks = read_jsonl(tasks_file)
    pending = {str(task["submit_id"]): task for task in tasks}
    completed: dict[str, list[Path]] = {}
    known_files = set(current_mp4s(videos_dir))
    started = time.monotonic()
    attempt = 0

    print(f"Waiting for {len(pending)} Dreamina task(s) to download into: {videos_dir}", flush=True)
    while pending:
        attempt += 1
        for submit_id, task in list(pending.items()):
            image_id = str(task.get("id") or submit_id)
            before = set(current_mp4s(videos_dir))
            returncode, output, payload = run_query(seedance_cli, submit_id, videos_dir)
            log_path = logs_dir / f"{image_id}.query.log"
            log_path.write_text(output, encoding="utf-8")

            status = str(payload.get("gen_status") or payload.get("status") or "").lower()
            if returncode != 0:
                print(f"{image_id}: query command failed; retrying after {args.poll_seconds}s", flush=True)
                continue
            if status == "fail":
                reason = payload.get("fail_reason") or payload.get("error") or output.strip()
                update_manifest(args.batch, image_id, "failed", submit_id, [], str(reason))
                raise SystemExit(f"{image_id} failed: {reason}")

            files = matching_downloads(videos_dir, submit_id, before | known_files)
            if status == "success" and files:
                completed[submit_id] = files
                pending.pop(submit_id)
                known_files.update(files)
                update_manifest(args.batch, image_id, "downloaded", submit_id, files, None)
                print(f"{image_id}: downloaded {len(files)} file(s).", flush=True)
            else:
                queue_status = ""
                queue_info = payload.get("queue_info")
                if isinstance(queue_info, dict):
                    queue_status = str(queue_info.get("queue_status") or "")
                detail = status or queue_status or "querying"
                print(f"{image_id}: {detail}; waiting.", flush=True)

        if pending:
            if args.timeout_seconds and time.monotonic() - started >= args.timeout_seconds:
                waiting = ", ".join(str(task.get("id") or submit_id) for submit_id, task in pending.items())
                raise SystemExit(f"Timed out waiting for videos: {waiting}")
            time.sleep(args.poll_seconds)

    all_files = sorted({path for files in completed.values() for path in files})
    print("")
    print(f"已生成完成，{len(all_files)} 个视频都已下载到:")
    for path in all_files:
        print(str(path))
    print("")
    print(f"状态检查: batch {args.batch} 现在有 videos: {len(current_mp4s(videos_dir))}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
