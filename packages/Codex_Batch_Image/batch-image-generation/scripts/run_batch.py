from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

RATIOS = {"21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"}
IMAGE_PROVIDERS = {"comfly-gemini-lite", "comfly-gpt-image-2", "apimart-gpt-image-2", "google-gemini-image", "dreamina-image"}
IMAGE_RESOLUTIONS = {"1K", "2K", "4K"}
DEFAULT_SECONDS_PER_IMAGE = 120.0
DEFAULT_DEADLINE_MULTIPLIER = 1.0
DEFAULT_COMPLETION_GRACE_SECONDS = 120.0


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def path_from(value: str | None, base: Path) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


class Store:
    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS jobs(
            job_key TEXT PRIMARY KEY, group_id TEXT NOT NULL, candidate_index INTEGER NOT NULL,
            prompt_sha256 TEXT NOT NULL, prompt_length INTEGER NOT NULL,
            status TEXT NOT NULL, started_at TEXT, finished_at TEXT,
            router_status TEXT, provider_id TEXT, model_id TEXT,
            source_output TEXT, collected_output TEXT, failure_class TEXT)""")
        self.db.commit()

    def add(self, key: str, group: str, index: int, prompt: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO jobs(job_key,group_id,candidate_index,prompt_sha256,prompt_length,status) VALUES(?,?,?,?,?,'pending')",
            (key, group, index, hashlib.sha256(prompt.encode()).hexdigest(), len(prompt)),
        )
        self.db.commit()

    def acquire(self, key: str) -> bool:
        self.db.execute("BEGIN IMMEDIATE")
        changed = self.db.execute(
            "UPDATE jobs SET status='running',started_at=? WHERE job_key=? AND status='pending'", (now_utc(), key)
        ).rowcount
        self.db.commit()
        return changed == 1

    def finish(self, key: str, status: str, **values: Any) -> None:
        allowed = {"router_status", "provider_id", "model_id", "source_output", "collected_output", "failure_class"}
        values = {key: value for key, value in values.items() if key in allowed}
        sets = ["status=?", "finished_at=?"] + [f"{key}=?" for key in values]
        self.db.execute(
            f"UPDATE jobs SET {','.join(sets)} WHERE job_key=? AND status IN ('pending','running')",
            [status, now_utc(), *values.values(), key],
        )
        self.db.commit()

    def abandon_pending(self) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute(
            "UPDATE jobs SET status='abandoned',finished_at=?,failure_class='batch_deadline_not_submitted' WHERE status='pending'",
            (now_utc(),),
        )
        self.db.commit()

    def fail_running_after_grace(self) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute(
            "UPDATE jobs SET status='failed',finished_at=?,failure_class='batch_completion_grace_timeout' WHERE status='running'",
            (now_utc(),),
        )
        self.db.commit()

    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute("SELECT * FROM jobs ORDER BY group_id,candidate_index")]


class StartGate:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.next_start = 0.0
        self.lock = asyncio.Lock()

    async def wait(self, deadline: float) -> bool:
        async with self.lock:
            delay = max(0.0, self.next_start - time.monotonic())
            if time.monotonic() + delay >= deadline:
                return False
            if delay:
                await asyncio.sleep(delay)
            started = time.monotonic()
            if started >= deadline:
                return False
            self.next_start = started + self.seconds
            return True


def validate(data: dict[str, Any]) -> None:
    if data.get("image_ratio") not in RATIOS:
        raise ValueError("an explicit supported image_ratio is required")
    if data.get("image_resolution") is not None and data["image_resolution"] not in IMAGE_RESOLUTIONS:
        raise ValueError("image_resolution must be 1K, 2K, or 4K")
    if data.get("image_provider") is not None and data["image_provider"] not in IMAGE_PROVIDERS:
        raise ValueError("image_provider must be a supported unified image route")
    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("groups must be a non-empty array")
    seen: set[str] = set()
    for group in groups:
        group_id = str(group.get("id", "")).strip()
        if not group_id or group_id in seen:
            raise ValueError("group ids must be non-empty and unique")
        seen.add(group_id)
        if not str(group.get("prompt", "")).strip() or int(group.get("candidates", 0)) < 1:
            raise ValueError(f"group {group_id} requires prompt and candidates >= 1")
    if not 1 <= int(data.get("concurrency", 10)) <= 10:
        raise ValueError("concurrency must be between 1 and 10")
    if float(data.get("start_delay_seconds", 1)) < 0:
        raise ValueError("start delay must be >= 0")
    if "seconds_per_image" in data and float(data["seconds_per_image"]) <= 0:
        raise ValueError("seconds_per_image must be > 0")
    if "deadline_multiplier" in data and float(data["deadline_multiplier"]) < 1:
        raise ValueError("deadline_multiplier must be >= 1")
    if "deadline_seconds" in data and float(data["deadline_seconds"]) <= 0:
        raise ValueError("deadline_seconds must be > 0")
    if "completion_grace_seconds" in data and not 0 < float(data["completion_grace_seconds"]) <= DEFAULT_COMPLETION_GRACE_SECONDS:
        raise ValueError("completion_grace_seconds must be > 0 and <= 120")


def resolve_timing(data: dict[str, Any], job_count: int) -> tuple[float, float]:
    # One to ten images always receive a full 120-second dispatch window.
    # Larger batches scale by 120 seconds per ten-image wave.
    expected_seconds = max(DEFAULT_SECONDS_PER_IMAGE, math.ceil(job_count / 10) * DEFAULT_SECONDS_PER_IMAGE)
    if "deadline_seconds" in data:
        return expected_seconds, float(data["deadline_seconds"])
    return expected_seconds, expected_seconds * float(data.get("deadline_multiplier", DEFAULT_DEADLINE_MULTIPLIER))


def providers_for_job(job: dict[str, Any]) -> list[str]:
    prompt = job["prompt"].casefold()
    local = ("局部修改", "局部调整", "元素替换", "替换元素", "真人角色", "真人")
    style = ("风格转换", "风格重绘", "画面重绘", "整体风格", "风格化", "风格迁移", "换画风", "换风格")
    if any(value in prompt for value in local):
        return ["comfly-gemini-lite", "comfly-gpt-image-2", "dreamina-image"]
    if any(value in prompt for value in style):
        return ["comfly-gpt-image-2", "comfly-gemini-lite", "dreamina-image"]
    if len(job.get("references", [])) > 1:
        digest = hashlib.sha256(job["prompt"].encode("utf-8")).hexdigest()
        first = "comfly-gemini-lite" if int(digest[-1], 16) % 2 == 0 else "comfly-gpt-image-2"
        second = "comfly-gpt-image-2" if first == "comfly-gemini-lite" else "comfly-gemini-lite"
        return [first, second, "dreamina-image"]
    return ["comfly-gpt-image-2", "comfly-gemini-lite", "dreamina-image"]


def router_result(stdout: bytes) -> dict[str, Any]:
    text = stdout.decode("utf-8", errors="replace")
    decoder = json.JSONDecoder()
    for offset, character in enumerate(text):
        if character != "{":
            continue
        try:
            result, end = decoder.raw_decode(text[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict) and not text[offset + end :].strip():
            return result
    raise ValueError("router returned no terminal JSON object")


async def kill_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec("taskkill", "/PID", str(process.pid), "/T", "/F", stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await killer.wait()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(process.wait(), 5)
    except asyncio.TimeoutError:
        process.kill()


async def generate(job: dict[str, Any], ratio: str, resolution: str | None, image_provider: str | None, router: Path, root: Path, store: Store, gate: StartGate, timeout_gate: asyncio.Semaphore, dispatch_deadline: float, completion_deadline: float) -> None:
    if not await gate.wait(dispatch_deadline):
        return
    if not store.acquire(job["key"]):
        return
    if time.monotonic() >= dispatch_deadline:
        store.finish(job["key"], "abandoned", failure_class="batch_deadline_not_submitted")
        return
    providers = [image_provider] if image_provider else providers_for_job(job)
    for attempt, provider_id in enumerate(providers):
        if time.monotonic() >= dispatch_deadline:
            store.finish(job["key"], "failed", failure_class="batch_completion_grace_timeout")
            return
        command = [sys.executable, "-B", str(router), "generate_image", "--prompt", job["prompt"], "--image-ratio", ratio, "--image-provider", provider_id]
        if resolution:
            command += ["--image-resolution", resolution]
        for reference in job["references"]:
            command += ["--image", str(reference)]
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0, start_new_session=os.name != "nt")
        timed_out = False
        try:
            remaining = min(120.0, completion_deadline - time.monotonic())
            if remaining <= 0:
                raise asyncio.TimeoutError
            stdout, _ = await asyncio.wait_for(process.communicate(), remaining)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            timed_out = True
            await kill_tree(process)
        if timed_out:
            if attempt == 0:
                async with timeout_gate:
                    continue
            continue
        try:
            result = router_result(stdout)
        except ValueError:
            continue
        source = Path(result["output_path"]) if result.get("output_path") else None
        if result.get("status") == "success" and source and source.is_file() and time.monotonic() <= completion_deadline:
            destination_dir = root / "results" / job["group"]
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"{job['index']:02d}{source.suffix.lower() or '.png'}"
            shutil.copy2(source, destination)
            store.finish(job["key"], "success", router_status="success", provider_id=result.get("provider_id"), model_id=result.get("model_id"), source_output=str(source.resolve()), collected_output=str(destination.resolve()))
            return
    store.finish(job["key"], "failed", failure_class="batch_completion_grace_timeout" if time.monotonic() >= completion_deadline else "router_failure")


def get_font(size: int) -> ImageFont.ImageFont:
    for candidate in (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def contact_sheet(group: dict[str, Any], ratio: str, base: Path, root: Path, successes: dict[int, Path]) -> Path:
    rw, rh = map(int, ratio.split(":"))
    width, height, label, gap, columns = 360, round(360 * rh / rw), 54, 20, 3
    original = path_from(group.get("original_image"), base)
    if original is None and group.get("reference_images"):
        original = path_from(group["reference_images"][0], base)
    slots = [("原始图", original)] + [(f"{i:02d}", successes.get(i)) for i in range(1, int(group["candidates"]) + 1)]
    rows = (len(slots) + columns - 1) // columns
    canvas = Image.new("RGB", (gap + columns * (width + gap), gap + rows * (height + label + gap)), "#202124")
    draw, label_font = ImageDraw.Draw(canvas), get_font(28)
    for slot, (text, source_path) in enumerate(slots):
        x = gap + slot % columns * (width + gap)
        y = gap + slot // columns * (height + label + gap)
        draw.rectangle((x, y, x + width, y + height), fill="#34363a")
        if source_path and source_path.is_file():
            try:
                with Image.open(source_path) as source:
                    canvas.paste(ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), (width, height), method=Image.Resampling.LANCZOS), (x, y))
            except OSError:
                source_path = None
        if not source_path or not source_path.is_file():
            draw.text((x + width / 2, y + height / 2), "未生成", anchor="mm", fill="#9aa0a6", font=label_font)
        draw.text((x + width / 2, y + height + 10), text, anchor="ma", fill="white", font=label_font)
    review = root / "review"
    review.mkdir(parents=True, exist_ok=True)
    output = review / f"{group['id']}_review.jpg"
    canvas.save(output, "JPEG", quality=92)
    return output.resolve()


async def run(data: dict[str, Any], manifest: Path, router: Path, dry_run: bool) -> dict[str, Any]:
    base = manifest.parent
    root = path_from(str(data.get("output_dir", "batch-output")), base)
    assert root is not None
    jobs = []
    version = str(data.get("prompt_version", "v1"))
    for group in data["groups"]:
        references = [path_from(value, base) for value in group.get("reference_images", [])]
        for index in range(1, int(group["candidates"]) + 1):
            jobs.append({"key": f"{data['batch_id']}:{group['id']}:{index}:{version}", "group": str(group["id"]), "index": index, "prompt": str(group["prompt"]), "references": [p for p in references if p]})
    expected_seconds, deadline_seconds = resolve_timing(data, len(jobs))
    completion_grace_seconds = float(data.get("completion_grace_seconds", DEFAULT_COMPLETION_GRACE_SECONDS))
    if dry_run:
        return {"status": "dry_run", "batch_id": data["batch_id"], "jobs": len(jobs), "groups": len(data["groups"]), "image_provider": data.get("image_provider"), "concurrency": int(data.get("concurrency", 10)), "start_delay_seconds": float(data.get("start_delay_seconds", 1)), "seconds_per_image": float(data.get("seconds_per_image", DEFAULT_SECONDS_PER_IMAGE)), "deadline_multiplier": float(data.get("deadline_multiplier", DEFAULT_DEADLINE_MULTIPLIER)), "expected_seconds": expected_seconds, "deadline_seconds": deadline_seconds, "completion_grace_seconds": completion_grace_seconds, "max_runtime_seconds": deadline_seconds + completion_grace_seconds, "output_dir": str(root)}
    root.mkdir(parents=True, exist_ok=True)
    store = Store(root / "batch-state.sqlite3")
    for job in jobs:
        store.add(job["key"], job["group"], job["index"], job["prompt"])
    dispatch_deadline = time.monotonic() + deadline_seconds
    completion_deadline = dispatch_deadline + completion_grace_seconds
    gate, semaphore, timeout_gate = StartGate(float(data.get("start_delay_seconds", 1))), asyncio.Semaphore(int(data.get("concurrency", 10))), asyncio.Semaphore(2)

    async def limited(job: dict[str, Any]) -> None:
        async with semaphore:
            await generate(job, data["image_ratio"], data.get("image_resolution"), data.get("image_provider"), router, root, store, gate, timeout_gate, dispatch_deadline, completion_deadline)

    tasks = [asyncio.create_task(limited(job)) for job in jobs]
    _, pending = await asyncio.wait(tasks, timeout=max(0, dispatch_deadline - time.monotonic()))
    if pending:
        store.abandon_pending()
        _, pending = await asyncio.wait(pending, timeout=max(0, completion_deadline - time.monotonic()))
        if pending:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            store.fail_running_after_grace()
    store.abandon_pending()
    rows = store.rows()
    successes: dict[str, dict[int, Path]] = {}
    for row in rows:
        if row["status"] == "success" and row["collected_output"]:
            successes.setdefault(row["group_id"], {})[row["candidate_index"]] = Path(row["collected_output"])
    sheets = [str(contact_sheet(group, data["image_ratio"], base, root, successes.get(str(group["id"]), {}))) for group in data["groups"]]
    counts = {state: sum(row["status"] == state for row in rows) for state in ("success", "failed", "abandoned")}
    summary = {"status": "complete", "batch_id": data["batch_id"], "expected_seconds": expected_seconds, "deadline_seconds": deadline_seconds, "completion_grace_seconds": completion_grace_seconds, "max_runtime_seconds": deadline_seconds + completion_grace_seconds, "counts": counts, "review_sheets": sheets, "output_dir": str(root.resolve())}
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    store.db.close()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Timed concurrent batch image generation")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--router")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        manifest = Path(args.manifest).resolve()
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        validate(data)
        data.setdefault("batch_id", f"batch-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}")
        default_router = Path(__file__).resolve().parents[3] / "Codex_image" / "CLI" / "Media-Router" / "media_router.py"
        router = Path(args.router).resolve() if args.router else default_router.resolve()
        if not args.dry_run and not router.is_file():
            raise ValueError(f"unified Media Router not found: {router}")
        print(json.dumps(asyncio.run(run(data, manifest, router, args.dry_run)), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "input_error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
