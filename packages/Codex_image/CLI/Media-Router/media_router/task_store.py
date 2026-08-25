from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import PRIVATE_ROOT
from .safe_logging import prompt_metadata, write_json
from .schemas import MediaRequest, TaskContext


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, private_root: Path = PRIVATE_ROOT):
        self.private_root = private_root.resolve()

    def create(self, request: MediaRequest, batch_id: str | None = None, task_id: str | None = None) -> TaskContext:
        batch_id = batch_id or f"batch-{uuid.uuid4().hex[:12]}"
        task_id = task_id or f"task-{uuid.uuid4().hex[:12]}"
        job_dir = self.private_root / "jobs" / batch_id / task_id
        output_dir = job_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=False)
        prompt_file = job_dir / "prompt.txt"
        prompt_file.write_text(request.prompt, encoding="utf-8")
        context = TaskContext(batch_id, task_id, job_dir, output_dir, prompt_file, job_dir / "cancel")
        write_json(job_dir / "request.json", {
            "task_id": task_id, "batch_id": batch_id, "prompt": prompt_metadata(request.prompt),
            "images": [str(p) for p in request.images], "videos": [str(p) for p in request.videos],
            "audios": [str(p) for p in request.audios], "image_ratio": request.image_ratio,
            "image_resolution": request.image_resolution, "image_provider": request.image_provider,
            "created_at": now(),
        })
        self.set_state(context, "pending")
        return context

    def set_state(self, context: TaskContext, status: str, **values) -> None:
        write_json(context.job_dir / "state.json", {"task_id": context.task_id, "status": status, "updated_at": now(), **values})

    def write_result(self, context: TaskContext, value: dict) -> None:
        write_json(context.job_dir / "result.json", value)

    def recovery_action(self, job_dir: Path) -> dict:
        state_path, result_path = job_dir / "state.json", job_dir / "result.json"
        if not state_path.is_file():
            return {"action": "needs_review", "reason": "missing_state"}
        state = __import__("json").loads(state_path.read_text(encoding="utf-8"))
        status = state.get("status")
        if status == "success" and result_path.is_file():
            return {"action": "return_result", "result_path": str(result_path)}
        if status in {"submitted", "failed", "needs_review", "cancelled"}:
            return {"action": "do_not_retry", "status": status}
        if status == "running":
            if state.get("submit_id"):
                return {"action": "resume_query", "submit_id": state["submit_id"]}
            return {"action": "needs_review", "reason": "running_without_provider_task_id"}
        return {"action": "execute" if status == "pending" else "needs_review", "reason": "unknown_state" if status != "pending" else None}
