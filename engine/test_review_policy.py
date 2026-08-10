import json
import os
import tempfile
import unittest
from pathlib import Path

from review_policy import (
    DEFAULT_REVIEW_POLICY,
    REVIEW_POLICY_KIND,
    REVIEW_POLICY_SCHEMA_VERSION,
    REVIEWER_REGISTRY_KIND,
    REVIEWER_REGISTRY_SCHEMA_VERSION,
    ReviewPolicyError,
    default_review_policy,
    load_review_policy,
    load_reviewer_registry,
    require_named_reviewer,
)


class ReviewPolicyTests(unittest.TestCase):
    def _write_sealed_json(self, path: Path, value: dict):
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)

    def _registry(self, policy_id: str) -> dict:
        return {
            "schema_version": REVIEWER_REGISTRY_SCHEMA_VERSION,
            "kind": REVIEWER_REGISTRY_KIND,
            "policy_id": policy_id,
            "reviewers": [{
                "id": "td_ana",
                "display_name": "Ana Technical Director",
                "roles": ["technical_director", "asset_reviewer"],
            }],
        }

    def test_default_policy_is_immutable_complete_and_stage_derived(self):
        policy = default_review_policy()
        self.assertIs(policy, DEFAULT_REVIEW_POLICY)
        self.assertEqual({gate.lane for gate in policy.gates}, {
            "input", "security", "geometry", "parts", "topology", "uv", "texture",
            "material", "memory", "package", "runtime", "license",
            "sufficient_real_evidence", "canonical_review",
        })
        self.assertEqual(policy.gate_for_lane("geometry").evidence_relative_path, "stages/geometry.json")
        with self.assertRaisesRegex(Exception, "cannot assign"):
            policy.policy_id = "unsafe"  # type: ignore[misc]

    def test_stage_evidence_is_strictly_job_local_and_missing_stages_block(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / "job"
            (job / "stages").mkdir(parents=True)
            policy = default_review_policy()
            paths = policy.stage_evidence_paths(job)
            self.assertEqual(paths["uv"], job.resolve() / "stages" / "uv.json")
            with self.assertRaisesRegex(ReviewPolicyError, "required_review_evidence_missing:canonical_review"):
                policy.require_stage_evidence(job)
            for path in paths.values():
                path.write_text("{}", encoding="utf-8")
            self.assertEqual(policy.require_stage_evidence(job), paths)
            with self.assertRaises(TypeError):
                paths["geometry"] = job  # type: ignore[index]

    def test_loads_sealed_policy_and_registry_then_resolves_named_reviewer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy_path = root / "review-policy.json"
            policy_document = {
                "schema_version": REVIEW_POLICY_SCHEMA_VERSION,
                "kind": REVIEW_POLICY_KIND,
                "policy_id": "custom_master_v1",
                "gates": [{"lane": gate.lane, "stage": f"proof_{gate.stage}"} for gate in DEFAULT_REVIEW_POLICY.gates],
            }
            self._write_sealed_json(policy_path, policy_document)
            policy = load_review_policy(policy_path)
            self.assertEqual(policy.gate_for_lane("canonical_review").evidence_relative_path, "stages/proof_canonical_review.json")
            registry_path = root / "reviewers.json"
            self._write_sealed_json(registry_path, self._registry(policy.policy_id))
            registry = load_reviewer_registry(registry_path, policy=policy)
            reviewer = require_named_reviewer(registry, "td_ana")
            self.assertEqual(reviewer.display_name, "Ana Technical Director")
            self.assertEqual(reviewer.roles, ("asset_reviewer", "technical_director"))

    def test_missing_or_mutable_policy_and_registry_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ReviewPolicyError, "review_policy_missing"):
                load_review_policy(root / "missing.json")
            mutable_policy = root / "mutable.json"
            document = {
                "schema_version": REVIEW_POLICY_SCHEMA_VERSION,
                "kind": REVIEW_POLICY_KIND,
                "policy_id": "custom_master_v1",
                "gates": [{"lane": gate.lane, "stage": gate.stage} for gate in DEFAULT_REVIEW_POLICY.gates],
            }
            mutable_policy.write_text(json.dumps(document), encoding="utf-8")
            mutable_policy.chmod(0o666)
            with self.assertRaisesRegex(ReviewPolicyError, "review_config_not_owner_controlled"):
                load_review_policy(mutable_policy)
            policy = default_review_policy()
            with self.assertRaisesRegex(ReviewPolicyError, "reviewer_registry_missing"):
                load_reviewer_registry(root / "missing-reviewers.json", policy=policy)

    def test_registry_wrong_policy_or_unknown_reviewer_never_degrades_to_allow(self):
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "reviewers.json"
            self._write_sealed_json(registry_path, self._registry("another_policy"))
            with self.assertRaisesRegex(ReviewPolicyError, "reviewer_registry_policy_mismatch"):
                load_reviewer_registry(registry_path, policy=default_review_policy())
            self._write_sealed_json(registry_path, self._registry(DEFAULT_REVIEW_POLICY.policy_id))
            registry = load_reviewer_registry(registry_path, policy=default_review_policy())
            with self.assertRaisesRegex(ReviewPolicyError, "unknown_reviewer"):
                require_named_reviewer(registry, "nobody")


if __name__ == "__main__":
    unittest.main()
