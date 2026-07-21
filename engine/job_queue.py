import asyncio
from collections import deque


class QueueFull(Exception):
    pass


class HeavyJobQueue:
    def __init__(self, jobs, runner, max_pending=1):
        self.jobs = jobs
        self.runner = runner
        self.max_pending = max_pending
        self.pending = deque()
        self.active_job_id = None
        self._lock = asyncio.Lock()
        self._worker_task = None

    def snapshot(self):
        return {
            "active_job_id": self.active_job_id,
            "pending": list(self.pending),
            "max_pending": self.max_pending,
        }

    async def submit(self, job_id, request):
        async with self._lock:
            if self.active_job_id and self._pending_count() >= self.max_pending:
                raise QueueFull("La cola 3D ya tiene un job activo y uno pendiente.")
            self.jobs[job_id] = {
                "status": "queued",
                "cancel_requested": False,
                "progress": 0,
                "stage": "En cola",
            }
            self.pending.append((job_id, request))
            self._refresh_positions()
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = asyncio.create_task(self._run())

    def _pending_count(self):
        return sum(
            1
            for job_id, _request in self.pending
            if not self.jobs.get(job_id, {}).get("cancel_requested")
        )

    def _refresh_positions(self):
        position = 0
        for job_id, _request in self.pending:
            job = self.jobs.get(job_id)
            if not job or job.get("cancel_requested"):
                continue
            position += 1
            job.update({"queue_position": position, "stage": f"En cola ({position})"})

    async def _run(self):
        while True:
            async with self._lock:
                while self.pending and self.jobs.get(self.pending[0][0], {}).get("cancel_requested"):
                    job_id, _request = self.pending.popleft()
                    self.jobs[job_id].update(
                        {
                            "status": "cancelled",
                            "stage": "Cancelado antes de iniciar",
                            "progress": 0,
                        }
                    )
                if not self.pending:
                    self.active_job_id = None
                    return
                job_id, request = self.pending.popleft()
                self.active_job_id = job_id
                self.jobs[job_id].update({"status": "running", "queue_position": 0})
                self._refresh_positions()

            try:
                await asyncio.to_thread(self.runner, job_id, request)
            finally:
                async with self._lock:
                    if self.active_job_id == job_id:
                        self.active_job_id = None
