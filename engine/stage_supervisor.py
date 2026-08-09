"""Bounded subprocess supervision for heavy, isolated Buffalo stages."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


class StageWorkerError(RuntimeError):
    def __init__(self, reason_code, stdout="", stderr=""):
        self.reason_code = reason_code
        self.stdout = stdout
        self.stderr = stderr
        diagnostic = (stdout + "\n" + stderr)[-5000:]
        super().__init__(f"stage_worker_failed:{reason_code}\n{diagnostic}".rstrip())


@dataclass(frozen=True)
class StageLimits:
    timeout_seconds: float = 1800.0
    poll_seconds: float = 2.0
    minimum_free_percent: float | None = 8.0
    maximum_swap_growth_mb: float | None = 2048.0
    network_allowed: bool = False


def offline_environment(base: Mapping[str, str] | None = None, *, network_allowed=False):
    environment = dict(base or os.environ)
    if not network_allowed:
        environment["HF_HUB_OFFLINE"] = "1"
        environment["TRANSFORMERS_OFFLINE"] = "1"
        # These are not a kernel sandbox. They remove common implicit network
        # routes; the process still needs OS-level sandboxing for a hard deny.
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            environment.pop(name, None)
    return environment


class StageSupervisor:
    """Terminate a worker before memory pressure makes the host unusable."""

    def __init__(self, snapshot: Callable[[], Mapping[str, float | None]]):
        self.snapshot = snapshot

    def run(self, command: Sequence[str], *, cwd, environment=None, limits=StageLimits()):
        baseline = dict(self.snapshot() or {})
        baseline_free = baseline.get("free_percent")
        if (
            limits.minimum_free_percent is not None
            and baseline_free is not None
            and baseline_free < limits.minimum_free_percent
        ):
            # Do not make a healthy host fight an inference job just to learn
            # it should be killed at the first watchdog tick.
            raise StageWorkerError("memory_admission")
        started = time.monotonic()
        minimum_free = baseline_free
        baseline_swap = baseline.get("swap_used_mb")
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=offline_environment(environment, network_allowed=limits.network_allowed),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout = stderr = ""
        reason = None
        while True:
            try:
                stdout, stderr = process.communicate(timeout=limits.poll_seconds)
                break
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - started
                current = dict(self.snapshot() or {})
                free_percent = current.get("free_percent")
                if free_percent is not None:
                    minimum_free = free_percent if minimum_free is None else min(minimum_free, free_percent)
                swap_used = current.get("swap_used_mb")
                if elapsed > limits.timeout_seconds:
                    reason = "timeout"
                elif (
                    limits.minimum_free_percent is not None
                    and free_percent is not None
                    and free_percent < limits.minimum_free_percent
                ):
                    reason = "memory_pressure"
                elif (
                    limits.maximum_swap_growth_mb is not None
                    and baseline_swap is not None
                    and swap_used is not None
                    and swap_used - baseline_swap > limits.maximum_swap_growth_mb
                ):
                    reason = "swap_growth_limit"
                if reason:
                    process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate()
                    raise StageWorkerError(reason, stdout, stderr)
        if process.returncode:
            raise StageWorkerError("nonzero_exit", stdout, stderr)
        return {
            "stdout": stdout,
            "stderr": stderr,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "baseline": baseline,
            "minimum_free_percent": minimum_free,
            "final": dict(self.snapshot() or {}),
        }
