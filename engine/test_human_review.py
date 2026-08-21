import json
import tempfile
import unittest
from pathlib import Path

from human_review import (
    APPROVE,
    REJECT,
    GateEvidenceSpec,
    HumanReviewError,
    Reviewer,
    seal_human_review,
    verify_human_review,
)


def _digest(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


class HumanReviewTests(unittest.TestCase):
    def _fixture(self, directory: str):
        job = Path(directory) / "job"
        job.mkdir()
        asset = job / "master.glb"
        asset.write_bytes(b"sealed-master-asset")
        digest = _digest(asset)
        gates = (
            GateEvidenceSpec("geometry", "gates/geometry.json", "geometry-gate"),
            GateEvidenceSpec("uv", "gates/uv.json", "uv-gate"),
            GateEvidenceSpec("canonical_review", "gates/canonical.json", "blender-canonical"),
        )
        for spec in gates:
            evidence = {
                "schema_version": 1,
                "kind": "gate_result",
                "producer": spec.producer,
                "status": "pass",
                "artifact": {"sha256": f"sha256:{digest}"},
            }
            target = job / spec.relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(evidence), encoding="utf-8")
        reviewers = (Reviewer("td-ana", "Ana Technical Director"),)
        return job, asset, gates, reviewers

    def test_named_approval_seals_all_passing_gates_and_promotes_master(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, gates, reviewers = self._fixture(directory)
            record = seal_human_review(
                job_dir=job,
                asset_path=asset,
                reviewer_id="td-ana",
                decision=APPROVE,
                required_gates=gates,
                reviewers=reviewers,
                note="Reviewed under neutral and grazing light.",
                clock=lambda: 1_700_000_000.0,
            )
            self.assertEqual(record["promotion"], "MASTER")
            self.assertEqual(record["reviewer"]["display_name"], "Ana Technical Director")
            self.assertEqual(record["asset"]["sha256"], f"sha256:{_digest(asset)}")
            review_path = next((job / "human-reviews").glob("*.json"))
            self.assertFalse(review_path.stat().st_mode & 0o222)
            verified = verify_human_review(
                job_dir=job, asset_path=asset, review_record_path=review_path,
                required_gates=gates, reviewers=reviewers,
            )
            self.assertEqual(verified, record)

    def test_fails_closed_when_a_required_gate_did_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, gates, reviewers = self._fixture(directory)
            bad = job / "gates/uv.json"
            evidence = json.loads(bad.read_text(encoding="utf-8"))
            evidence["status"] = "attention"
            bad.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaisesRegex(HumanReviewError, "gate_not_passed:uv"):
                seal_human_review(
                    job_dir=job, asset_path=asset, reviewer_id="td-ana", decision=APPROVE,
                    required_gates=gates, reviewers=reviewers,
                )

    def test_rejects_unknown_or_forged_evidence_before_it_can_be_sealed(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, gates, reviewers = self._fixture(directory)
            forged = job / "gates/geometry.json"
            evidence = json.loads(forged.read_text(encoding="utf-8"))
            evidence["producer"] = "untrusted-worker"
            forged.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaisesRegex(HumanReviewError, "unknown_gate_evidence:geometry"):
                seal_human_review(
                    job_dir=job, asset_path=asset, reviewer_id="td-ana", decision=APPROVE,
                    required_gates=gates, reviewers=reviewers,
                )

    def test_verification_detects_evidence_or_asset_changed_after_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, gates, reviewers = self._fixture(directory)
            record = seal_human_review(
                job_dir=job, asset_path=asset, reviewer_id="td-ana", decision=APPROVE,
                required_gates=gates, reviewers=reviewers,
            )
            review_path = job / "human-reviews" / f"{record['record_id'].removeprefix('sha256:')}.json"
            geometry = job / "gates/geometry.json"
            evidence = json.loads(geometry.read_text(encoding="utf-8"))
            evidence["producer"] = "forged-after-review"
            geometry.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaisesRegex(HumanReviewError, "unknown_gate_evidence:geometry"):
                verify_human_review(
                    job_dir=job, asset_path=asset, review_record_path=review_path,
                    required_gates=gates, reviewers=reviewers,
                )
            # Restore the report, then prove a replacement asset cannot inherit
            # its prior human decision.
            evidence["producer"] = "geometry-gate"
            geometry.write_text(json.dumps(evidence), encoding="utf-8")
            asset.write_bytes(b"replacement-asset")
            with self.assertRaisesRegex(HumanReviewError, "review_record_asset_mismatch"):
                verify_human_review(
                    job_dir=job, asset_path=asset, review_record_path=review_path,
                    required_gates=gates, reviewers=reviewers,
                )

    def test_unknown_reviewer_cannot_promote_and_rejection_is_never_master(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, gates, reviewers = self._fixture(directory)
            with self.assertRaisesRegex(HumanReviewError, "unknown_reviewer"):
                seal_human_review(
                    job_dir=job, asset_path=asset, reviewer_id="someone-else", decision=APPROVE,
                    required_gates=gates, reviewers=reviewers,
                )
            rejected = seal_human_review(
                job_dir=job, asset_path=asset, reviewer_id="td-ana", decision=REJECT,
                required_gates=gates, reviewers=reviewers,
            )
            self.assertEqual(rejected["promotion"], "NON_MASTER")


if __name__ == "__main__":
    unittest.main()
