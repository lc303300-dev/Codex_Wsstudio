from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import time

from .safe_logging import write_json


class ProviderRuntime:
    def __init__(self, root: Path, provider_id: str, failure_threshold: int = 3, cooldown_seconds: int = 60):
        self.directory = root / provider_id
        self.state_path = self.directory / "health.json"
        self.metrics_path = self.directory / "metrics.json"
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

    def _read(self, path: Path, default: dict) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return default.copy()

    def readiness(self) -> tuple[bool, str | None]:
        state = self._read(self.state_path, {})
        opened_at = state.get("circuit_opened_at_epoch")
        if opened_at and time() - float(opened_at) < self.cooldown_seconds:
            return False, "Provider circuit is temporarily open"
        return True, None

    def record(self, success: bool, duration_ms: int = 0) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        state = self._read(self.state_path, {"consecutive_failures": 0})
        metrics = self._read(self.metrics_path, {"attempts": 0, "successes": 0, "failures": 0, "duration_ms": 0})
        metrics["attempts"] += 1
        metrics["duration_ms"] += max(0, duration_ms)
        if success:
            metrics["successes"] += 1
            state = {"consecutive_failures": 0, "circuit_opened_at_epoch": None}
        else:
            metrics["failures"] += 1
            state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
            if state["consecutive_failures"] >= self.failure_threshold:
                state["circuit_opened_at_epoch"] = time()
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        metrics["updated_at"] = state["updated_at"]
        write_json(self.state_path, state)
        write_json(self.metrics_path, metrics)
