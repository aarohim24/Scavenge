"""Minimal process-tree measurement for benchmark tasks.

The benchmark records wall time, CPU time, and RSS at the task boundary. For
Playwright tasks this includes Chromium child processes because the benchmark
measures the whole process tree, not just the Python interpreter.
"""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class ProcessTreeSnapshot:
    cpu_time_seconds: float
    rss_bytes: int


def snapshot_process_tree() -> ProcessTreeSnapshot:
    process = psutil.Process()
    processes = [process, *process.children(recursive=True)]
    seen_pids: set[int] = set()
    cpu_time_seconds = 0.0
    rss_bytes = 0

    for child in processes:
        if child.pid in seen_pids:
            continue
        seen_pids.add(child.pid)
        try:
            cpu_times = child.cpu_times()
            memory_info = child.memory_info()
        except psutil.Error:
            continue
        cpu_time_seconds += cpu_times.user + cpu_times.system
        rss_bytes += memory_info.rss

    return ProcessTreeSnapshot(cpu_time_seconds=cpu_time_seconds, rss_bytes=rss_bytes)
