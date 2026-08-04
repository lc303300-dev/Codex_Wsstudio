from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .errors import FailureClass, MediaRouterError


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


@dataclass
class SlotLease:
    root: Path
    capacity_key: str
    task_id: str
    slots: int = 6
    wait_timeout: float = 180.0
    stale_after: float = 600.0
    cancel_path: Path | None = None
    path: Path | None = None

    def _payload(self) -> bytes:
        now = datetime.now(timezone.utc).isoformat()
        return json.dumps({"pid": os.getpid(), "task_id": self.task_id, "created_at": now, "heartbeat_at": now}).encode("utf-8")

    def _reclaim_stale(self, path: Path) -> None:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            age = time.time() - path.stat().st_mtime
            if age > self.stale_after and not _pid_exists(int(record.get("pid", -1))):
                path.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            return

    def acquire(self) -> "SlotLease":
        directory = self.root / self.capacity_key
        directory.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.wait_timeout
        while True:
            if self.cancel_path and self.cancel_path.exists():
                raise MediaRouterError("Task was cancelled while waiting for provider capacity", FailureClass.CANCELLED)
            for number in range(1, self.slots + 1):
                candidate = directory / f"slot-{number}.lock"
                self._reclaim_stale(candidate)
                try:
                    descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    continue
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(self._payload())
                self.path = candidate
                return self
            if time.monotonic() >= deadline:
                raise MediaRouterError("Timed out before acquiring a provider slot", FailureClass.TIMEOUT_BEFORE_SUBMIT)
            time.sleep(0.05)

    def heartbeat(self) -> None:
        if self.path:
            os.utime(self.path, None)

    def release(self) -> None:
        if self.path:
            self.path.unlink(missing_ok=True)
            self.path = None

    def __enter__(self) -> "SlotLease":
        return self.acquire()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()
