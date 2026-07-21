import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from job_logging import append_job_log


class JobLoggingTest(unittest.TestCase):
    def test_append_job_log_writes_bounded_jsonl_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = append_job_log(Path(tmp), "job-1", "stage", stage="Preparando", duration=1.2)
            rows = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 1)
            payload = json.loads(rows[0])
            self.assertEqual(payload["job_id"], "job-1")
            self.assertEqual(payload["event"], "stage")
            self.assertEqual(payload["stage"], "Preparando")
            self.assertEqual(payload["duration"], 1.2)


if __name__ == "__main__":
    unittest.main()
