import tempfile
import unittest
from pathlib import Path

from adversarial_asset_corpus import (
    AdversarialCorpusError,
    corpus_cases,
    materialize_corpus,
    run_adversarial_asset_corpus,
)


class AdversarialAssetCorpusTests(unittest.TestCase):
    def test_required_local_corpus_passes_and_rejects_every_malicious_case(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run_adversarial_asset_corpus(directory)
        self.assertTrue(report["passed"])
        self.assertEqual(report["execution"], "local_deterministic")
        malicious = [case for case in report["cases"] if case["malicious"]]
        self.assertTrue(malicious)
        self.assertTrue(all(case["classification"] == "reject" for case in malicious))
        self.assertTrue(all(case["conforms"] for case in report["cases"]))
        self.assertEqual(next(case for case in report["cases"] if not case["malicious"])["classification"], "pass")

    def test_materialized_payloads_are_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            entries_a = materialize_corpus(first)
            entries_b = materialize_corpus(second)
            self.assertEqual(entries_a, entries_b)
            self.assertEqual(
                (Path(first) / "control-minimal-triangle.glb").read_bytes(),
                (Path(second) / "control-minimal-triangle.glb").read_bytes(),
            )
            self.assertEqual(
                run_adversarial_asset_corpus(first)["corpus_sha256"],
                run_adversarial_asset_corpus(second)["corpus_sha256"],
            )

    def test_accepting_a_required_malicious_case_raises_fail_closed_error(self):
        def permissive_container(_path):
            return {"nodes": 1, "images": 0, "bytes": 1}

        def permissive_certificate(_path, _target):
            return {"status": "pass"}

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AdversarialCorpusError, "malicious-external-texture-uri"):
                run_adversarial_asset_corpus(
                    directory,
                    container_validator=permissive_container,
                    certificate_validator=permissive_certificate,
                )

    def test_corpus_case_ids_are_stable_and_unique(self):
        ids = [case.case_id for case in corpus_cases()]
        self.assertEqual(ids, [
            "control-minimal-triangle",
            "malicious-external-texture-uri",
            "malicious-invalid-header-length",
            "malicious-invalid-json",
            "malicious-trailing-byte",
            "malicious-missing-default-scene",
            "malicious-buffer-view-out-of-bounds",
            "malicious-invalid-node-reference",
        ])
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
