import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_asset.py"
SPEC = importlib.util.spec_from_file_location("audit_asset", SCRIPT)
audit_asset = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(audit_asset)


class AuditAssetTests(unittest.TestCase):
    def test_audit_reports_present_controls_and_never_invents_physical_measurements(self):
        root = Path(__file__).resolve().parents[1]
        report = audit_asset.audit(root)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(all(item["present"] for item in report["controls"].values()))
        self.assertIn("device_runtime_execution", report["not_measured"])
        self.assertGreater(len(report["asset_director"]["plans"]), 5)
        crane = report["asset_director"]["plans"]["crane"]
        self.assertGreaterEqual(crane["required_parts"], 7)
        self.assertGreaterEqual(crane["critical_parts"], 7)
        self.assertEqual(crane["semantic_evidence_status"], "not_measured")

    def test_missing_engine_controls_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            report = audit_asset.audit(Path(directory))
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(not item["present"] for item in report["controls"].values()))


if __name__ == "__main__":
    unittest.main()
