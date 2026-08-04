from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "CLI" / "Media-Router"))

from media_router.concurrency import SlotLease

lock_root, task_id, hold_seconds = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
with SlotLease(lock_root, "cross-process", task_id, wait_timeout=10):
    print("acquired", flush=True)
    time.sleep(hold_seconds)
