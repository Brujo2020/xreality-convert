import asyncio
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from job_queue import HeavyJobQueue, QueueFull


class HeavyJobQueueTest(unittest.IsolatedAsyncioTestCase):
    async def test_limits_to_one_active_and_one_pending_job(self):
        jobs = {}
        started = asyncio.Event()
        release = threading.Event()
        calls = []

        def runner(job_id, request):
            calls.append((job_id, request))
            self.loop.call_soon_threadsafe(started.set)
            release.wait(timeout=1)
            jobs[job_id].update({"status": "done", "progress": 100})

        self.loop = asyncio.get_running_loop()
        queue = HeavyJobQueue(jobs, runner, max_pending=1)

        await queue.submit("active", {"kind": "shape"})
        await started.wait()
        await queue.submit("pending", {"kind": "shape"})

        with self.assertRaises(QueueFull):
            await queue.submit("rejected", {"kind": "shape"})

        self.assertEqual(jobs["active"]["status"], "running")
        self.assertEqual(jobs["pending"]["status"], "queued")
        self.assertNotIn("rejected", jobs)

        release.set()
        await asyncio.sleep(0.05)
        self.assertEqual(calls[0][0], "active")
        self.assertEqual(calls[1][0], "pending")

    async def test_cancelled_pending_job_is_skipped(self):
        jobs = {}
        started = asyncio.Event()
        release = threading.Event()
        calls = []

        def runner(job_id, request):
            calls.append(job_id)
            self.loop.call_soon_threadsafe(started.set)
            release.wait(timeout=1)
            jobs[job_id].update({"status": "done"})

        self.loop = asyncio.get_running_loop()
        queue = HeavyJobQueue(jobs, runner, max_pending=1)

        await queue.submit("active", {})
        await started.wait()
        await queue.submit("pending", {})
        jobs["pending"]["cancel_requested"] = True
        release.set()
        await asyncio.sleep(0.05)

        self.assertEqual(calls, ["active"])
        self.assertEqual(jobs["pending"]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
