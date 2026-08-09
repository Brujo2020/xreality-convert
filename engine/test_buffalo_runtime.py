import base64
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from buffalo_runtime import (
    ContractError,
    JobLedger,
    build_evidence_manifest,
    build_job_contract,
    decode_base64_image,
)


class BuffaloRuntimeTests(unittest.TestCase):
    def test_image_decoder_rejects_invalid_base64(self):
        with self.assertRaisesRegex(ContractError, "invalid_image_base64"):
            decode_base64_image("not base64!")

    def test_contract_and_ledger_are_durable_and_ordered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.png"
            image = Image.new("RGBA", (32, 32), "red")
            image.save(input_path)
            evidence = build_evidence_manifest(input_path, {"format": "PNG", "width": 32, "height": 32})
            contract = build_job_contract(
                job_id="a" * 32,
                request={"profile": "xreal", "target_faces": 1000, "texture_resolution": 1024},
                evidence_manifest=evidence,
                semantic_contract={"category": "product"},
                execution_policy={"material_contract": {}, "deadline_seconds": 60},
            )
            ledger = JobLedger(root, "a" * 32)
            ledger.seal(contract, evidence)
            ledger.transition("PREFLIGHTED", "input_admitted")
            ledger.transition("RUNNING_STAGE", "shape_started")
            stage = ledger.record_stage("shape", "passed", {"seed": 42})
            ledger.transition("STAGE_PASSED", "shape_passed")

            self.assertEqual(ledger.state, "STAGE_PASSED")
            self.assertTrue(stage.is_file())
            self.assertEqual(json.loads(ledger.contract_path.read_text())["job_id"], "a" * 32)
            events = ledger.journal_path.read_text().strip().splitlines()
            self.assertEqual(len(events), 4)
            self.assertEqual(json.loads(events[-1])["to"], "STAGE_PASSED")

            loaded = JobLedger.load(root, "a" * 32)
            self.assertEqual(loaded.state, "STAGE_PASSED")

    def test_ledger_rejects_invalid_transition_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = JobLedger(directory, "b" * 32)
            with self.assertRaisesRegex(ContractError, "invalid_transition"):
                ledger.transition("MASTER", "no_shortcut")
            with self.assertRaisesRegex(ContractError, "unsafe_job_id"):
                JobLedger(directory, "../../escape")
