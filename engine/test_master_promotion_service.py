import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from buffalo_runtime import canonical_json
from human_review import APPROVE, REJECT
from master_promotion_service import (
    DEFAULT_GATE_PRODUCERS,
    MASTER_PROMOTION_KIND,
    MasterPromotionError,
    seal_master_promotion,
    verify_master_promotion,
)
from review_policy import (
    DEFAULT_REVIEW_POLICY,
    REVIEW_POLICY_KIND,
    REVIEW_POLICY_SCHEMA_VERSION,
    REVIEWER_REGISTRY_KIND,
    REVIEWER_REGISTRY_SCHEMA_VERSION,
)
from review_gate_evidence import (
    GATE_SOURCE_CLASS,
    GATE_SOURCE_KIND,
    GATE_EVIDENCE_SCHEMA_VERSION,
    seal_gate_result,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MasterPromotionServiceTests(unittest.TestCase):
    def _write_sealed_json(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        path.chmod(0o400)

    def _fixture(self, directory: str):
        root = Path(directory)
        job = root / "4f78d08b-c2e3-42fb-86f2-f701a96f5cc3"
        (job / "stages").mkdir(parents=True)
        asset = job / "master.glb"
        asset.write_bytes(b"master-local-asset")
        digest = _digest(asset)
        policy_path = root / "review-policy.json"
        policy_document = {
            "schema_version": REVIEW_POLICY_SCHEMA_VERSION,
            "kind": REVIEW_POLICY_KIND,
            "policy_id": "review_master_local_v1",
            "gates": [{"lane": gate.lane, "stage": gate.stage} for gate in DEFAULT_REVIEW_POLICY.gates],
        }
        self._write_sealed_json(policy_path, policy_document)
        registry_path = root / "reviewers.json"
        registry_document = {
            "schema_version": REVIEWER_REGISTRY_SCHEMA_VERSION,
            "kind": REVIEWER_REGISTRY_KIND,
            "policy_id": "review_master_local_v1",
            "reviewers": [{
                "id": "td_ana",
                "display_name": "Ana Technical Director",
                "roles": ["technical_director", "asset_reviewer"],
            }],
        }
        self._write_sealed_json(registry_path, registry_document)
        for gate in DEFAULT_REVIEW_POLICY.gates:
            source_payload = {
                "schema_version": GATE_EVIDENCE_SCHEMA_VERSION,
                "kind": GATE_SOURCE_KIND,
                "evidence_class": GATE_SOURCE_CLASS,
                "producer": DEFAULT_GATE_PRODUCERS[gate.lane],
                "lane": gate.lane,
                "status": "pass",
                "artifact": {"sha256": f"sha256:{digest}"},
            }
            source = {**source_payload, "source_id": "sha256:" + hashlib.sha256(canonical_json(source_payload)).hexdigest()}
            source_path = job / "gate-sources" / f"{gate.lane}.json"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_sealed_json(source_path, source)
            seal_gate_result(job_dir=job, asset_path=asset, lane=gate.lane, stage=gate.stage)
        return job, asset, policy_path, registry_path

    def _approve(self, job: Path, asset: Path, policy_path: Path, registry_path: Path):
        return seal_master_promotion(
            job_dir=job,
            asset_path=asset,
            reviewer_id="td_ana",
            decision=APPROVE,
            policy_path=policy_path,
            reviewer_registry_path=registry_path,
            note="Revisión neutral, base color y luz rasante completada.",
            clock=lambda: 1_700_000_000.0,
        )

    def test_named_human_approval_with_all_policy_gates_is_the_only_master_path(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, policy_path, registry_path = self._fixture(directory)
            record = self._approve(job, asset, policy_path, registry_path)
            self.assertEqual(record["kind"], MASTER_PROMOTION_KIND)
            self.assertEqual(record["promotion"], "MASTER")
            self.assertEqual(record["approval"], "named_human")
            self.assertEqual(record["human_review"]["reviewer_id"], "td_ana")
            promotion_path = next((job / "master-promotions").glob("*.json"))
            self.assertFalse(promotion_path.stat().st_mode & 0o222)
            self.assertEqual(
                verify_master_promotion(
                    job_dir=job, asset_path=asset, promotion_record_path=promotion_path,
                    policy_path=policy_path, reviewer_registry_path=registry_path,
                ),
                record,
            )

    def test_rejection_is_durable_non_master_and_missing_decision_never_auto_approves(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, policy_path, registry_path = self._fixture(directory)
            with self.assertRaisesRegex(MasterPromotionError, "explicit_review_decision_required"):
                seal_master_promotion(
                    job_dir=job, asset_path=asset, reviewer_id="td_ana", decision="",
                    policy_path=policy_path, reviewer_registry_path=registry_path,
                )
            record = seal_master_promotion(
                job_dir=job, asset_path=asset, reviewer_id="td_ana", decision=REJECT,
                policy_path=policy_path, reviewer_registry_path=registry_path,
                clock=lambda: 1_700_000_000.0,
            )
            self.assertEqual(record["promotion"], "NON_MASTER")
            self.assertEqual(record["approval"], "named_human_rejection")

    def test_mutable_local_config_or_unregistered_reviewer_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, policy_path, registry_path = self._fixture(directory)
            policy_path.chmod(0o600)
            with self.assertRaisesRegex(MasterPromotionError, "review_policy_not_sealed"):
                self._approve(job, asset, policy_path, registry_path)
            policy_path.chmod(0o400)
            with self.assertRaisesRegex(MasterPromotionError, "unknown_reviewer"):
                seal_master_promotion(
                    job_dir=job, asset_path=asset, reviewer_id="untrusted",
                    decision=APPROVE, policy_path=policy_path, reviewer_registry_path=registry_path,
                )

    def test_policy_or_registry_rotation_after_approval_invalidates_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, policy_path, registry_path = self._fixture(directory)
            record = self._approve(job, asset, policy_path, registry_path)
            promotion_path = job / "master-promotions" / f"{record['record_id'].removeprefix('sha256:')}.json"
            policy_path.chmod(0o600)
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["gates"] = [
                {"lane": gate.lane, "stage": ("proof_geometry" if gate.lane == "geometry" else gate.stage)}
                for gate in DEFAULT_REVIEW_POLICY.gates
            ]
            self._write_sealed_json(policy_path, policy)
            with self.assertRaisesRegex(MasterPromotionError, "master_promotion_policy_mismatch"):
                verify_master_promotion(
                    job_dir=job, asset_path=asset, promotion_record_path=promotion_path,
                    policy_path=policy_path, reviewer_registry_path=registry_path,
                )
            # Restore policy, mutate the still-sealed registry identity, and
            # demonstrate that named human identity cannot be swapped later.
            policy_path.chmod(0o600)
            policy["gates"] = [{"lane": gate.lane, "stage": gate.stage} for gate in DEFAULT_REVIEW_POLICY.gates]
            self._write_sealed_json(policy_path, policy)
            registry_path.chmod(0o600)
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["reviewers"][0]["display_name"] = "Different reviewer"
            self._write_sealed_json(registry_path, registry)
            with self.assertRaisesRegex(MasterPromotionError, "master_promotion_reviewer_registry_mismatch"):
                verify_master_promotion(
                    job_dir=job, asset_path=asset, promotion_record_path=promotion_path,
                    policy_path=policy_path, reviewer_registry_path=registry_path,
                )

    def test_gate_or_asset_mutation_after_approval_is_detected_before_master_use(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, policy_path, registry_path = self._fixture(directory)
            record = self._approve(job, asset, policy_path, registry_path)
            promotion_path = job / "master-promotions" / f"{record['record_id'].removeprefix('sha256:')}.json"
            geometry = job / "stages" / "geometry.json"
            geometry.chmod(0o600)
            with self.assertRaisesRegex(MasterPromotionError, "gate_evidence_invalid:geometry"):
                verify_master_promotion(
                    job_dir=job, asset_path=asset, promotion_record_path=promotion_path,
                    policy_path=policy_path, reviewer_registry_path=registry_path,
                )
            geometry.chmod(0o400)
            asset.write_bytes(b"replacement-local-asset")
            with self.assertRaisesRegex(MasterPromotionError, "master_promotion_asset_mismatch"):
                verify_master_promotion(
                    job_dir=job, asset_path=asset, promotion_record_path=promotion_path,
                    policy_path=policy_path, reviewer_registry_path=registry_path,
                )

    def test_only_one_promotion_decision_can_be_sealed_for_a_job(self):
        with tempfile.TemporaryDirectory() as directory:
            job, asset, policy_path, registry_path = self._fixture(directory)
            self._approve(job, asset, policy_path, registry_path)
            with self.assertRaisesRegex(MasterPromotionError, "master_promotion_already_exists"):
                self._approve(job, asset, policy_path, registry_path)


if __name__ == "__main__":
    unittest.main()
