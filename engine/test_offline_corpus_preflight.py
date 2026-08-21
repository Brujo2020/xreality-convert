import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from offline_campaign import EXPECTED_CASE_IDS
from offline_corpus_preflight import (
    CorpusPreflightError,
    build_preflight_manifest,
    campaign_asset_hashes,
    verify_preflight_against_corpus,
    verify_preflight_manifest_seal,
    write_preflight_manifest,
)


def _case(case_id, *, master=False):
    inputs = [{"relative_path": f"inputs/{case_id}-front.png", "kind": "image", "identity_stratum": "real", "observed": True}]
    if master:
        inputs.append({"relative_path": f"inputs/{case_id}-back.png", "kind": "image", "identity_stratum": "real", "observed": True})
    return {
        "case_id": case_id,
        "delivery_intent": "master" if master else "preview",
        "source_identity_stratum": "real",
        "legal": {
            "license": {"status": "verified", "reference": "local-test-license"},
            "consent": {"status": "verified", "reference": "local-test-consent"},
        },
        "evidence": {"sufficiency": "sufficient", "reference": "local test capture record"},
        "observed_view_count": len(inputs),
        "inputs": inputs,
    }


def _inventory(*, master_case=None):
    return {case_id: _case(case_id, master=case_id == master_case) for case_id in EXPECTED_CASE_IDS}


def _write_inputs(root, inventory):
    for case in inventory.values():
        for entry in case["inputs"]:
            path = root / entry["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((case["case_id"] + entry["relative_path"]).encode("utf-8"))


class OfflineCorpusPreflightTests(unittest.TestCase):
    def test_builds_exact_30_case_local_hash_bound_inventory_and_revalidates_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = _inventory(master_case=EXPECTED_CASE_IDS[0])
            _write_inputs(root, inventory)
            manifest = build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=inventory)
            self.assertTrue(verify_preflight_manifest_seal(manifest))
            self.assertTrue(verify_preflight_against_corpus(manifest=manifest, corpus_root=root))
            self.assertEqual([case["case_id"] for case in manifest["cases"]], list(EXPECTED_CASE_IDS))
            hashes = campaign_asset_hashes(manifest)
            self.assertEqual(set(hashes), set(EXPECTED_CASE_IDS))
            first = manifest["cases"][0]
            self.assertEqual(hashes[first["case_id"]], first["asset"]["sha256"])
            (root / first["inputs"][0]["relative_path"]).write_bytes(b"tampered")
            self.assertFalse(verify_preflight_against_corpus(manifest=manifest, corpus_root=root))

    def test_master_rejects_single_or_non_real_observed_view_and_insufficient_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = _inventory(master_case=EXPECTED_CASE_IDS[0])
            _write_inputs(root, inventory)
            bad = copy.deepcopy(inventory)
            bad[EXPECTED_CASE_IDS[0]]["inputs"] = bad[EXPECTED_CASE_IDS[0]]["inputs"][:1]
            bad[EXPECTED_CASE_IDS[0]]["observed_view_count"] = 1
            with self.assertRaisesRegex(CorpusPreflightError, "two_real_observed"):
                build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=bad)
            bad = copy.deepcopy(inventory)
            bad[EXPECTED_CASE_IDS[0]]["evidence"]["sufficiency"] = "insufficient"
            with self.assertRaisesRegex(CorpusPreflightError, "evidence_insufficient"):
                build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=bad)
            bad = copy.deepcopy(inventory)
            bad[EXPECTED_CASE_IDS[0]]["inputs"][1]["identity_stratum"] = "synthetic"
            with self.assertRaisesRegex(CorpusPreflightError, "two_real_observed"):
                build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=bad)

    def test_rejects_incomplete_inventory_unsafe_paths_mismatched_observation_and_unverified_legal_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = _inventory()
            _write_inputs(root, inventory)
            incomplete = dict(inventory)
            incomplete.pop(EXPECTED_CASE_IDS[-1])
            with self.assertRaisesRegex(CorpusPreflightError, "inventory_mismatch"):
                build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=incomplete)
            bad = copy.deepcopy(inventory)
            bad[EXPECTED_CASE_IDS[0]]["inputs"][0]["relative_path"] = "../outside.png"
            with self.assertRaisesRegex(CorpusPreflightError, "relative_path_invalid"):
                build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=bad)
            bad = copy.deepcopy(inventory)
            bad[EXPECTED_CASE_IDS[0]]["observed_view_count"] = 2
            with self.assertRaisesRegex(CorpusPreflightError, "observed_view_count_mismatch"):
                build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=bad)
            bad = copy.deepcopy(inventory)
            bad[EXPECTED_CASE_IDS[0]]["legal"]["license"]["status"] = "claimed"
            with self.assertRaisesRegex(CorpusPreflightError, "legal_status_invalid"):
                build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=bad)

    def test_seal_detects_manifest_tampering_and_persistence_is_exclusive_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = _inventory()
            _write_inputs(root, inventory)
            manifest = build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=inventory)
            tampered = copy.deepcopy(manifest)
            tampered["cases"][0]["inputs"][0]["sha256"] = "sha256:" + "0" * 64
            self.assertFalse(verify_preflight_manifest_seal(tampered))
            destination = root / "sealed-preflight.json"
            written = write_preflight_manifest(manifest=manifest, destination=destination)
            self.assertEqual(written, destination)
            self.assertEqual(destination.stat().st_mode & 0o222, 0)
            with self.assertRaisesRegex(CorpusPreflightError, "destination_unsafe_or_exists"):
                write_preflight_manifest(manifest=manifest, destination=destination)

    def test_manifest_digest_is_deterministic_for_identical_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inventory = _inventory()
            _write_inputs(root, inventory)
            first = build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=inventory)
            second = build_preflight_manifest(campaign_id="buffalo-corpus-v1", corpus_root=root, cases=inventory)
            self.assertEqual(first["seal"]["value"], second["seal"]["value"])
            self.assertEqual(hashlib.sha256(first["seal"]["value"].encode()).hexdigest(), hashlib.sha256(second["seal"]["value"].encode()).hexdigest())


if __name__ == "__main__":
    unittest.main()
