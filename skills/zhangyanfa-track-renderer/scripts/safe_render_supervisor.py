#!/usr/bin/env python3
"""Run render tasks sequentially with resource checks and resumable receipts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock_path = Path(__file__).resolve().parents[2] / 'zhangyanfa-video-production/scripts/heavy_job.py'
_lock_loader = importlib.util.spec_from_file_location('production_heavy_job', _lock_path)
_job_guard = importlib.util.module_from_spec(_lock_loader)
_lock_loader.loader.exec_module(_job_guard)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command_sha(command: list[str]) -> str:
    return hashlib.sha256(json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def memory_free_percent() -> float | None:
    try:
        result = subprocess.run(
            ["/usr/bin/memory_pressure", "-Q"], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
        )
        match = re.search(r"free percentage:\s*([0-9.]+)%", result.stdout)
        return float(match.group(1)) if match else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def swap_used_gib() -> float | None:
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "vm.swapusage"], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
        )
        match = re.search(r"used = ([0-9.]+)([MG])", result.stdout)
        if not match:
            return None
        value = float(match.group(1))
        return value / 1024 if match.group(2) == "M" else value
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def group_rss_gib(pgid: int) -> float | None:
    try:
        result = subprocess.run(
            ["/bin/ps", "-axo", "pgid=,rss="], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
        )
        kib = 0
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and int(parts[0]) == pgid:
                kib += int(parts[1])
        return kib / 1024 / 1024
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def stop_group(process: subprocess.Popen[Any], grace_seconds: float = 8.0) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + grace_seconds
    while process.poll() is None and time.time() < deadline:
        time.sleep(0.25)
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def valid_receipt(path: Path, task: dict[str, Any], fingerprint: str | None = None) -> bool:
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fingerprint = fingerprint or task_fingerprint(task)
        output = Path(str(task["output"])).expanduser().resolve()
        return (
            data.get("status") == "PASS"
            and data.get("task_id") == task.get("task_id")
            and bool(fingerprint)
            and data.get("task_fingerprint") == fingerprint
            and output.is_file()
            and data.get("output_sha256") == sha256_file(output)
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False


def task_fingerprint(task: dict[str, Any], digest_cache=None) -> str | None:
    """A legacy output-only receipt is not evidence that the inputs still match."""
    refs = task.get('input_bindings')
    if not isinstance(refs, list) or not refs or not task.get('tool_versions'):
        return None
    for ref in refs:
        path = Path(ref['path']).expanduser().resolve()
        stat = path.stat()
        key = (str(path), stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        actual = digest_cache.get(key) if digest_cache is not None else None
        if actual is None:
            actual = sha256_file(path)
            if digest_cache is not None:
                digest_cache[key] = actual
        if actual != ref.get('sha256'):
            raise ValueError(f'render input changed: {path}')
    return hashlib.sha256(json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def run_attempt(
    task: dict[str, Any], attempt: dict[str, Any], config: dict[str, Any],
    log_path: Path, lock_fd: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    command = attempt.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise ValueError("attempt.command must be a nonempty string list")
    output = Path(str(task["output"])).expanduser().resolve()
    progress = Path(str(attempt.get("progress_path") or output)).expanduser().resolve()
    wrapped = command
    if Path("/usr/bin/caffeinate").is_file():
        wrapped = ["/usr/bin/caffeinate", "-dimsu", "--", *command]
    samples: list[dict[str, Any]] = []
    started = now()
    last_progress = time.time()
    prior_marker: tuple[int, ...] | None = None
    reason = ""
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            wrapped, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, cwd=attempt.get("cwd"),
            pass_fds=(lock_fd,) if lock_fd is not None else (),
        )
        while process.poll() is None:
            free_gib = shutil.disk_usage(Path(config["scratch_root"])).free / 1024**3
            free_percent = memory_free_percent()
            swap = swap_used_gib()
            rss = group_rss_gib(process.pid)
            marker_parts: list[int] = []
            for candidate in (progress, log_path):
                if candidate.exists():
                    stat = candidate.stat()
                    marker_parts.extend((stat.st_size, stat.st_mtime_ns))
            marker = tuple(marker_parts) if marker_parts else None
            if marker is not None and marker != prior_marker:
                prior_marker = marker
                last_progress = time.time()
            sample = {
                "at": now(), "free_disk_gib": round(free_gib, 3),
                "memory_free_percent": free_percent, "swap_used_gib": swap,
                "process_group_rss_gib": rss,
            }
            samples.append(sample)
            samples = samples[-240:]
            if free_gib < float(config["minimum_free_gib"]):
                reason = "disk_reserve_crossed"
            elif free_percent is not None and free_percent < float(config.get("minimum_memory_free_percent", 8.0)):
                reason = "memory_pressure_threshold"
            elif config.get("maximum_swap_used_gib") is not None and swap is not None and swap > float(config["maximum_swap_used_gib"]):
                reason = "swap_threshold"
            elif config.get("maximum_process_rss_gib") is not None and rss is not None and rss > float(config["maximum_process_rss_gib"]):
                reason = "process_rss_threshold"
            elif time.time() - last_progress > float(config.get("stall_timeout_seconds", 900)):
                reason = "progress_stall"
            if reason:
                stop_group(process)
                break
            time.sleep(float(config.get("poll_seconds", 5)))
        return_code = process.wait()
    passed = return_code == 0 and output.is_file() and output.stat().st_size > 0
    if not passed and not reason:
        reason = f"exit_{return_code}" if return_code else "missing_output"
    return passed, {
        "started_at": started, "ended_at": now(), "command": command,
        "command_sha256": command_sha(command), "return_code": return_code,
        "stop_reason": reason, "samples": samples,
    }


def main(lock_fd: int | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    config = json.loads(args.plan.read_text(encoding="utf-8"))
    scratch = Path(str(config.get("scratch_root", ""))).expanduser().resolve()
    if "Mobile Documents/com~apple~CloudDocs" in str(scratch):
        raise SystemExit("scratch_root must be local and outside iCloud Drive")
    scratch.mkdir(parents=True, exist_ok=True)
    receipts = Path(str(config.get("receipts_dir", scratch / "receipts"))).expanduser().resolve()
    logs = Path(str(config.get("logs_dir", scratch / "logs"))).expanduser().resolve()
    receipts.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    tasks = config.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        raise SystemExit("plan requires nonempty tasks")
    track_order = {"A": 0, "B": 1, "C": 2, "FINAL": 3}
    if [track_order.get(str(task.get("track")), 99) for task in tasks] != sorted(track_order.get(str(task.get("track")), 99) for task in tasks):
        raise SystemExit("tasks must be ordered A -> B -> C -> FINAL")

    digest_cache = {}
    for task in tasks:
        task_id = str(task.get("task_id", "")).strip()
        if not task_id or "output" not in task:
            raise SystemExit("every task requires task_id and output")
        fingerprint = task_fingerprint(task, digest_cache)
        if config.get('production_contract_version') == 2 and fingerprint is None:
            raise SystemExit('v2 tasks require actual input_bindings and tool_versions before rendering')
        receipt_path = receipts / f"{task_id}.json"
        if valid_receipt(receipt_path, task, fingerprint):
            continue
        attempts = task.get("attempts", [])
        if not isinstance(attempts, list) or not attempts:
            raise SystemExit(f"task {task_id} requires attempts")
        attempt_reports: list[dict[str, Any]] = []
        passed = False
        for index, attempt in enumerate(attempts, 1):
            log_path = logs / f"{task_id}.attempt-{index}.log"
            passed, report = run_attempt(task, attempt, config, log_path, lock_fd)
            report["attempt"] = index
            report["log_path"] = str(log_path)
            attempt_reports.append(report)
            if passed:
                break
            cooldown = float(attempt.get("cooldown_seconds", config.get("cooldown_seconds", 30)))
            if index < len(attempts) and cooldown > 0:
                time.sleep(cooldown)
        output = Path(str(task["output"])).expanduser().resolve()
        receipt = {
            "task_id": task_id,
            "track": task.get("track"),
            "status": "PASS" if passed else "FAIL",
            "output": str(output),
            "output_sha256": sha256_file(output) if passed else None,
            "attempts": attempt_reports,
            "written_at": now(),
            "task_fingerprint": fingerprint,
        }
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        if not passed:
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return 1
    return 0


if __name__ == "__main__":
    try:
        with _job_guard.heavy_lock() as lock_fd:
            raise SystemExit(main(lock_fd))
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(75)
