import os
import sys
import tempfile
import unittest

from stage_supervisor import StageLimits, StageSupervisor, StageWorkerError, offline_environment


class StageSupervisorTests(unittest.TestCase):
    def test_offline_environment_removes_common_proxy_routes(self):
        environment = offline_environment({"HTTPS_PROXY": "https://proxy", "KEEP": "yes"})
        self.assertEqual(environment["HF_HUB_OFFLINE"], "1")
        self.assertNotIn("HTTPS_PROXY", environment)
        self.assertEqual(environment["KEEP"], "yes")

    def test_worker_captures_result_in_offline_mode(self):
        supervisor = StageSupervisor(lambda: {"free_percent": 50.0, "swap_used_mb": 1.0})
        with tempfile.TemporaryDirectory() as directory:
            result = supervisor.run(
                [sys.executable, "-c", "import os; assert os.environ['HF_HUB_OFFLINE'] == '1'; print('ok')"],
                cwd=directory,
                limits=StageLimits(timeout_seconds=5, poll_seconds=0.05),
            )
        self.assertIn("ok", result["stdout"])

    def test_worker_terminates_on_memory_pressure(self):
        snapshots = iter((
            {"free_percent": 50.0, "swap_used_mb": 1.0},
            {"free_percent": 2.0, "swap_used_mb": 1.0},
        ))
        supervisor = StageSupervisor(lambda: next(snapshots))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(StageWorkerError, "memory_pressure"):
                supervisor.run(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    cwd=directory,
                    limits=StageLimits(timeout_seconds=5, poll_seconds=0.02),
                )

    def test_worker_is_not_started_when_memory_admission_fails(self):
        supervisor = StageSupervisor(lambda: {"free_percent": 2.0, "swap_used_mb": 1.0})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(StageWorkerError, "memory_admission"):
                supervisor.run(
                    [sys.executable, "-c", "raise SystemExit('should not run')"],
                    cwd=directory,
                    limits=StageLimits(timeout_seconds=5, poll_seconds=0.02),
                )
