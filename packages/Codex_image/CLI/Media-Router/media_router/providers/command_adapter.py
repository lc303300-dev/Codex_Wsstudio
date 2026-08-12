from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import PRIVATE_ROOT, PROJECT_ROOT
from ..errors import FailureClass, MediaRouterError
from ..output_validation import is_valid_image, is_valid_video
from ..provider_runtime import ProviderRuntime
from ..safe_logging import safe_text, write_json
from ..schemas import MediaRequest, ProviderResult, Readiness, TaskContext
from .comfly_common import load_dotenv


def _env() -> dict[str, str]:
    value = os.environ.copy()
    value["PYTHONDONTWRITEBYTECODE"] = "1"
    return value


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False, timeout=10)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _remaining_timeout(context: TaskContext, default: float) -> float:
    return max(0.001, min(default, context.provider_deadline - time.monotonic())) if context.provider_deadline is not None else default


def _run(command: list[str], timeout: float, log_path: Path, submitted_on_start: bool = True, timeout_failure: FailureClass | None = None) -> subprocess.CompletedProcess:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        failure = timeout_failure or (FailureClass.INDETERMINATE_SUBMISSION if submitted_on_start else FailureClass.TIMEOUT_BEFORE_SUBMIT)
        raise MediaRouterError("Provider command timed out", failure, submitted=submitted_on_start) from exc
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    write_json(log_path, {"exit_code": completed.returncode, "transcript": "<redacted>", "output_characters": len(completed.stdout), "error_characters": len(completed.stderr)})
    if completed.returncode:
        combined = (completed.stdout + "\n" + completed.stderr).lower()
        failure = FailureClass.TIMEOUT_BEFORE_SUBMIT if not submitted_on_start and any(word in combined for word in ("timed out", "timeout", "did not complete")) else FailureClass.INDETERMINATE_SUBMISSION if any(word in combined for word in ("timed out", "timeout", "did not complete")) else FailureClass.AUTH_UNAVAILABLE if any(word in combined for word in ("login", "unauthorized", "api_key", "not configured")) else FailureClass.QUOTA_UNAVAILABLE if any(word in combined for word in ("quota", "credit", "insufficient")) else FailureClass.POLICY_REJECTION if any(word in combined for word in ("policy", "safety", "compliance")) else FailureClass.DEFINITE_PROVIDER_FAILURE if any(word in combined for word in ('"gen_status":"failed"', '"status":"failed"', "task ended with status failed", "http 5")) else FailureClass.INDETERMINATE_SUBMISSION
        raise MediaRouterError("Provider command failed", failure, submitted=submitted_on_start)
    return completed


class PythonImageAdapter:
    capability = "image"

    def __init__(self, provider_id: str, model_id: str, script: Path, key_name: str | None, max_concurrency: int = 6):
        self.provider_id, self.model_id, self.script, self.key_name = provider_id, model_id, script, key_name
        self.capacity_key, self.max_concurrency = provider_id, max_concurrency
        self.runtime = ProviderRuntime(PRIVATE_ROOT / "logs" / "providers", provider_id)

    def check_readiness(self) -> Readiness:
        available, reason = self.runtime.readiness()
        if not available:
            return Readiness(False, reason)
        if self.key_name:
            configured = bool(os.environ.get(self.key_name) or load_dotenv(PRIVATE_ROOT / ".env").get(self.key_name))
            return Readiness(configured, None if configured else f"{self.key_name} is not configured")
        executable = PRIVATE_ROOT / "bin" / "gemini-cli" / "agy.exe"
        return Readiness(executable.is_file(), None if executable.is_file() else "Antigravity CLI is not installed")

    def execute(self, request: MediaRequest, context: TaskContext) -> ProviderResult:
        start, stamp = time.monotonic(), datetime.now(timezone.utc).isoformat()
        output = context.output_dir / f"{self.provider_id}.png"
        log = context.job_dir / "logs" / f"{self.provider_id}.json"
        command = ["py", "-3", str(self.script), "--prompt-file", str(context.prompt_file), "--out", str(output), "--log", str(log)]
        for image in request.images:
            command += ["--image", str(image)]
        if self.provider_id == "apimart-gpt-image-2":
            command += ["--model", self.model_id, "--workspace", str(PRIVATE_ROOT)]
        elif self.provider_id == "google-gemini-image":
            command += ["--model", self.model_id, "--env-file", str(PRIVATE_ROOT / ".env")]
        try:
            _run(command, _remaining_timeout(context, 420), log, timeout_failure=FailureClass.PROVIDER_TIMEOUT if context.provider_deadline is not None else None)
            if not is_valid_image(output):
                raise MediaRouterError("Provider produced no valid local image", FailureClass.DOWNLOAD_FAILURE, submitted=True)
            duration = int((time.monotonic()-start)*1000)
            self.runtime.record(True, duration)
            return ProviderResult(self.provider_id, self.model_id, "success", output_path=str(output), output_bytes=output.stat().st_size, started_at=stamp, finished_at=datetime.now(timezone.utc).isoformat(), duration_ms=duration)
        except MediaRouterError as exc:
            duration = int((time.monotonic()-start)*1000)
            self.runtime.record(False, duration)
            status = "needs_review" if exc.failure_class == FailureClass.INDETERMINATE_SUBMISSION else "failed"
            return ProviderResult(self.provider_id, self.model_id, status, failure_class=exc.failure_class, safe_reason=str(exc), started_at=stamp, finished_at=datetime.now(timezone.utc).isoformat(), duration_ms=duration)


class DreaminaAdapter:
    capacity_key = "seedance-cli"
    max_concurrency = 6

    def __init__(self, provider_id: str, capability: str, model_id: str):
        self.provider_id, self.capability, self.model_id = provider_id, capability, model_id
        self.runner = PROJECT_ROOT / "CLI" / "Seedance-CLI" / "run.ps1"
        self.runtime = ProviderRuntime(PRIVATE_ROOT / "logs" / "providers", provider_id)

    def check_readiness(self) -> Readiness:
        available, reason = self.runtime.readiness()
        if not available:
            return Readiness(False, reason)
        executable = PRIVATE_ROOT / "bin" / "seedance-cli" / "dreamina.exe"
        return Readiness(executable.is_file(), None if executable.is_file() else "Dreamina CLI is not installed")

    def _query_and_download(self, submit_id: str, context: TaskContext, media_type: str) -> Path:
        target = context.output_dir / self.provider_id
        target.mkdir(parents=True, exist_ok=True)
        deadline = min(time.monotonic() + 420, context.provider_deadline) if context.provider_deadline is not None else time.monotonic() + 420
        while time.monotonic() < deadline:
            timeout_failure = FailureClass.PROVIDER_TIMEOUT if context.provider_deadline is not None else None
            result = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.runner), "query_result", "--submit_id", submit_id, "--download_dir", str(target)], _remaining_timeout(context, 90), context.job_dir / "logs" / f"{self.provider_id}-query.json", timeout_failure=timeout_failure)
            candidates = [p for p in target.rglob("*") if p.is_file()]
            validator = is_valid_image if media_type == "image" else is_valid_video
            valid = next((p for p in candidates if validator(p)), None)
            if valid:
                return valid
            combined = (result.stdout + result.stderr).lower()
            if any(word in combined for word in ('"failed"', "gen_status: failed", "cancelled")):
                raise MediaRouterError("Dreamina task ended unsuccessfully", FailureClass.DEFINITE_PROVIDER_FAILURE, submitted=True)
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        if context.provider_deadline is not None:
            raise MediaRouterError("Image provider exceeded its deadline", FailureClass.PROVIDER_TIMEOUT, submitted=True)
        raise MediaRouterError("Dreamina task may still be running", FailureClass.INDETERMINATE_SUBMISSION, submitted=True)

    @staticmethod
    def _submit_id(text: str) -> str | None:
        match = re.search(r'(?i)["\']?submit_id["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]+)', text)
        return match.group(1) if match else None

    def execute_command(self, command_name: str, arguments: list[str], request: MediaRequest, context: TaskContext) -> ProviderResult:
        started, stamp = time.monotonic(), datetime.now(timezone.utc).isoformat()
        requested_model = self.model_id
        if "--model_version" in arguments:
            model_index = arguments.index("--model_version") + 1
            if model_index < len(arguments):
                requested_model = arguments[model_index]
        help_log = context.job_dir / "logs" / f"{self.provider_id}-help.json"
        try:
            timeout_failure = FailureClass.PROVIDER_TIMEOUT if context.provider_deadline is not None else None
            _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.runner), command_name, "-h"], _remaining_timeout(context, 60), help_log, submitted_on_start=False, timeout_failure=timeout_failure)
            _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.runner), "user_credit"], _remaining_timeout(context, 30), context.job_dir / "logs" / f"{self.provider_id}-credit.json", submitted_on_start=False, timeout_failure=timeout_failure)
            completed = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.runner), command_name, *arguments], _remaining_timeout(context, 240), context.job_dir / "logs" / f"{self.provider_id}-submit.json", timeout_failure=timeout_failure)
            submit_id = self._submit_id(completed.stdout + "\n" + completed.stderr)
            if not submit_id:
                raise MediaRouterError("Dreamina submission returned no submit_id", FailureClass.INDETERMINATE_SUBMISSION, submitted=True)
            write_json(context.job_dir / "state.json", {"task_id": context.task_id, "status": "running", "submit_id": submit_id, "updated_at": datetime.now(timezone.utc).isoformat()})
            output = self._query_and_download(submit_id, context, self.capability)
            duration = int((time.monotonic()-started)*1000)
            self.runtime.record(True, duration)
            return ProviderResult(self.provider_id, requested_model, "success", submit_id=submit_id, output_path=str(output), output_bytes=output.stat().st_size, started_at=stamp, finished_at=datetime.now(timezone.utc).isoformat(), duration_ms=duration)
        except MediaRouterError as exc:
            duration = int((time.monotonic()-started)*1000)
            self.runtime.record(False, duration)
            status = "needs_review" if exc.failure_class == FailureClass.INDETERMINATE_SUBMISSION else "cancelled" if exc.failure_class == FailureClass.CANCELLED else "failed"
            return ProviderResult(self.provider_id, requested_model, status, failure_class=exc.failure_class, safe_reason=str(exc), started_at=stamp, finished_at=datetime.now(timezone.utc).isoformat(), duration_ms=duration)

    def execute(self, request: MediaRequest, context: TaskContext) -> ProviderResult:
        if self.capability == "image":
            command = "image2image" if request.images else "text2image"
            model = request.image_model or "4.0"
            resolution = "1k" if model == "5.0Pro" else "2k"
            args = ["--prompt", request.prompt, "--model_version", model, "--resolution_type", resolution, "--generate_num", "1", "--poll", "180"]
            if request.images:
                args += ["--images", ",".join(str(p) for p in request.images)]
            return self.execute_command(command, args, request, context)
        raise NotImplementedError("Video commands are selected by VideoRouter")
