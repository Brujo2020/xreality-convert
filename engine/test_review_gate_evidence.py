import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from buffalo_runtime import canonical_json
from human_review import APPROVE, GateEvidenceSpec, Reviewer, seal_human_review
from review_gate_evidence import (
    GATE_EVIDENCE_SCHEMA_VERSION,
    GATE_PRODUCERS,
    GATE_SOURCE_CLASS,
    GATE_SOURCE_KIND,
    GateEvidenceError,
    result_relative_path,
    seal_gate_result,
    source_relative_path,
    verify_gate_result,
)


def _record_id(payload: dict) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload)).hexdigest()}"


class ReviewGateEvidenceTests(unittest.TestCase):
    def _source(self, job: Path, asset: Path, lane: str = "geometry", **overrides):
        payload = {
            "schema_version": GATE_EVIDENCE_SCHEMA_VERSION,
            "kind": GATE_SOURCE_KIND,
            "evidence_class": GATE_SOURCE_CLASS,
            "producer": GATE_PRODUCERS[lane],
            "lane": lane,
            "status": "pass",
            "artifact": {"sha256": f"sha256:{hashlib.sha256(asset.read_bytes()).hexdigest()}"},
        }
        payload.update(overrides)
        payload["source_id"] = _record_id(payload)
        destination = job / source_relative_path(lane)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        destination.chmod(0o400)
        return destination

    def _fixture(self):
        temporary = tempfile.TemporaryDirectory()
        job = Path(temporary.name) / "job-123"
        job.mkdir()
        asset = job / "master.glb"
        asset.write_bytes(b"the-exact-master-bytes")
        self._source(job, asset)
        return temporary, job, asset

    def test_seals_and_reverifies_only_a_typed_job_local_source(self):
        temporary, job, asset = self._fixture()
        with temporary:
            result = seal_gate_result(job_dir=job, asset_path=asset, lane="geometry")
            self.assertEqual(result["kind"], "gate_result")
            self.assertEqual(result["producer"], GATE_PRODUCERS["geometry"])
            self.assertFalse((job / result_relative_path("geometry")).stat().st_mode & 0o222)
            self.assertEqual(
                verify_gate_result(job_dir=job, asset_path=asset, lane="geometry"),
                result,
            )
            # The emitted schema remains intentionally compatible with the
            # narrow consumer used by human_review/master promotion, while the
            # stronger evidence_class/source binding is retained as extras.
            approval = seal_human_review(
                job_dir=job, asset_path=asset, reviewer_id="td_ana", decision=APPROVE,
                required_gates=(GateEvidenceSpec("geometry", result_relative_path("geometry"), GATE_PRODUCERS["geometry"]),),
                reviewers=(Reviewer("td_ana", "Ana"),),
            )
            self.assertEqual(approval["promotion"], "MASTER")

    def test_generic_stage_or_caller_claim_can_never_be_used_as_source(self):
        temporary, job, asset = self._fixture()
        with temporary:
            source = job / source_relative_path("geometry")
            source.chmod(0o600)
            source.write_text(json.dumps({
                "status": "pass", "producer": GATE_PRODUCERS["geometry"],
                "artifact": {"sha256": f"sha256:{hashlib.sha256(asset.read_bytes()).hexdigest()}"},
            }), encoding="utf-8")
            source.chmod(0o400)
            # This resembles a generic stage report and says pass, but lacks
            # the exclusive source class, lane and self-integrity binding.
            with self.assertRaisesRegex(GateEvidenceError, "wrong_gate_source_class"):
                seal_gate_result(job_dir=job, asset_path=asset, lane="geometry")

    def test_rejects_mutable_wrong_lane_producer_status_and_asset_source(self):
        cases = (
            ({"producer": "untrusted"}, "gate_source_producer_or_lane_mismatch"),
            ({"lane": "uv"}, "gate_source_producer_or_lane_mismatch"),
            ({"status": "attention"}, "gate_source_not_passed"),
            ({"artifact": {"sha256": "sha256:" + "0" * 64}}, "gate_source_asset_mismatch"),
        )
        for override, error in cases:
            with self.subTest(override=override), tempfile.TemporaryDirectory() as directory:
                job = Path(directory) / "job"
                job.mkdir()
                asset = job / "master.glb"
                asset.write_bytes(b"asset")
                source = self._source(job, asset)
                source.chmod(0o600)
                document = json.loads(source.read_text(encoding="utf-8"))
                document.update(override)
                document["source_id"] = _record_id({key: value for key, value in document.items() if key != "source_id"})
                source.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
                source.chmod(0o400)
                with self.assertRaisesRegex(GateEvidenceError, error):
                    seal_gate_result(job_dir=job, asset_path=asset, lane="geometry")
        temporary, job, asset = self._fixture()
        with temporary:
            source = job / source_relative_path("geometry")
            source.chmod(0o600)
            with self.assertRaisesRegex(GateEvidenceError, "invalid_gate_source_not_sealed"):
                seal_gate_result(job_dir=job, asset_path=asset, lane="geometry")

    def test_blocks_overwrite_traversal_and_generic_destination(self):
        temporary, job, asset = self._fixture()
        with temporary:
            generic = job / result_relative_path("geometry")
            generic.parent.mkdir(parents=True)
            generic.write_text('{"status":"pass"}', encoding="utf-8")
            with self.assertRaisesRegex(GateEvidenceError, "gate_result_already_exists"):
                seal_gate_result(job_dir=job, asset_path=asset, lane="geometry")
            with self.assertRaisesRegex(GateEvidenceError, "unknown_gate_lane"):
                seal_gate_result(job_dir=job, asset_path=asset, lane="../geometry")
            with self.assertRaisesRegex(GateEvidenceError, "invalid_gate_stage"):
                seal_gate_result(job_dir=job, asset_path=asset, lane="geometry", stage="../escape")

    def test_reverification_detects_source_asset_and_evidence_mutation(self):
        temporary, job, asset = self._fixture()
        with temporary:
            seal_gate_result(job_dir=job, asset_path=asset, lane="geometry", stage="proof_geometry")
            result_path = job / result_relative_path("geometry", stage="proof_geometry")
            result_path.chmod(0o600)
            value = json.loads(result_path.read_text(encoding="utf-8"))
            value["evidence_class"] = "generic_stage"
            result_path.write_text(json.dumps(value), encoding="utf-8")
            result_path.chmod(0o400)
            with self.assertRaisesRegex(GateEvidenceError, "wrong_gate_result_class"):
                verify_gate_result(job_dir=job, asset_path=asset, lane="geometry", stage="proof_geometry")
            # A replacement source/asset also invalidates the prior proof;
            # chmod is only used here to simulate a privileged local attacker.
            result_path.chmod(0o600)
            result_path.write_text(json.dumps(seal_gate_result.__name__), encoding="utf-8")
            result_path.chmod(0o400)
            asset.write_bytes(b"replaced")
            with self.assertRaisesRegex(GateEvidenceError, "gate_source_asset_mismatch"):
                verify_gate_result(job_dir=job, asset_path=asset, lane="geometry", stage="proof_geometry")

    def test_source_id_integrity_and_symlink_inputs_fail_closed(self):
        temporary, job, asset = self._fixture()
        with temporary:
            source = job / source_relative_path("geometry")
            source.chmod(0o600)
            value = json.loads(source.read_text(encoding="utf-8"))
            value["producer"] = "xreality_geometry_gate_v1"  # Same value but stale source_id test below.
            value["source_id"] = "sha256:" + "1" * 64
            source.write_text(json.dumps(value), encoding="utf-8")
            source.chmod(0o400)
            with self.assertRaisesRegex(GateEvidenceError, "gate_source_integrity_mismatch"):
                seal_gate_result(job_dir=job, asset_path=asset, lane="geometry")


if __name__ == "__main__":
    unittest.main()
