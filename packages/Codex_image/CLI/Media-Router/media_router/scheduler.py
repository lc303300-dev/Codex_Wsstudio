from __future__ import annotations

from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def rolling_map(tasks: Iterable[T], runner: Callable[[T], R], runtime_slots: int, configured_limit: int = 6) -> list[R]:
    limit = min(6, configured_limit, max(1, runtime_slots))
    pending = deque(tasks)
    active: dict[Future, int] = {}
    results: list[tuple[int, R]] = []
    with ThreadPoolExecutor(max_workers=limit) as pool:
        next_index = 0
        while pending or active:
            while pending and len(active) < limit:
                task = pending.popleft()
                future = pool.submit(runner, task)
                active[future] = next_index
                next_index += 1
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                results.append((active.pop(future), future.result()))
    return [value for _, value in sorted(results)]
