import copy
import hashlib
import unittest

from offline_campaign import (
    CampaignIntegrityError,
    EXPECTED_CASE_IDS,
    REQUIRED_GATES,
    build_campaign_manifest,
    evaluate_offline_campaign,
    seal_case_report,
    verify_campaign_manifest_seal,
)


def _asset_hash(case_id):
    return "sha256:" + hashlib.sha256(case_id.encode("utf-8")).hexdigest()


def _manifest():
    return build_campaign_manifest("buffalo-local-acceptance-v1", {case_id: _asset_hash(case_id) for case_id in EXPECTED_CASE_IDS})


def _report(manifest, case_id, *, gates=None, metrics=None):
    asset_hash = next(case["asset"]["sha256"] for case in manifest["cases"] if case["case_id"] == case_id)
    gate_values = gates or {
        gate: {"status": "pass", "evidence_class": "measured", "asset_sha256": asset_hash}
        for gate in REQUIRED_GATES
    }
    metric_values = metrics or {
        "latency_seconds": {"status": "measured", "value": 1.25},
        "peak_memory_bytes": {"status": "measured", "value": 4096},
    }
    return seal_case_report({
        "schema_version": 1,
        "campaign_id": manifest["campaign_id"],
        "case_id": case_id,
        "execution": {"offline": True, "network_allowed": False},
        "asset": {"sha256": asset_hash},
        "gates": gate_values,
        "metrics": metric_values,
    })


class OfflineCampaignTests(unittest.TestCase):
    def test_full_30_case_campaign_is_stable_and_aggregates_only_measured_metrics(self):
        manifest = _manifest()
        reports = [_report(manifest, case_id) for case_id in EXPECTED_CASE_IDS]
        reports[0] = _report(manifest, EXPECTED_CASE_IDS[0], metrics={
            "latency_seconds": {"status": "not_measured"},
            "peak_memory_bytes": {"status": "measured", "value": 8192},
        })
        report = evaluate_offline_campaign(manifest, reports)
        self.assertTrue(verify_campaign_manifest_seal(manifest))
        self.assertTrue(report["passed"])
        self.assertEqual(report["case_count"], 30)
        self.assertEqual(report["gate_aggregate"], {"total": 180, "measured_pass": 180, "measured_fail": 0, "measured_inconclusive": 0, "not_measured": 0})
        self.assertEqual(report["metrics"]["latency_seconds"]["measured_cases"], 29)
        self.assertEqual(report["metrics"]["latency_seconds"]["not_measured_cases"], 1)
        self.assertEqual(report["metrics"]["peak_memory_bytes"]["max"], 8192)
        self.assertEqual(report["campaign_sha256"], evaluate_offline_campaign(manifest, reports)["campaign_sha256"])

    def test_not_measured_and_inconclusive_gate_are_distinct_and_block_strict_pass(self):
        manifest = _manifest()
        reports = [_report(manifest, case_id) for case_id in EXPECTED_CASE_IDS]
        first = EXPECTED_CASE_IDS[0]
        asset_hash = manifest["cases"][0]["asset"]["sha256"]
        reports[0] = _report(manifest, first, gates={
            **{gate: {"status": "pass", "evidence_class": "measured", "asset_sha256": asset_hash} for gate in REQUIRED_GATES},
            "texture": {"status": "not_measured", "evidence_class": "not_measured", "asset_sha256": asset_hash},
            "canonical_review": {"status": "inconclusive", "evidence_class": "measured", "asset_sha256": asset_hash},
        })
        report = evaluate_offline_campaign(manifest, reports)
        self.assertFalse(report["passed"])
        self.assertEqual(report["gate_aggregate"]["not_measured"], 1)
        self.assertEqual(report["gate_aggregate"]["measured_inconclusive"], 1)
        self.assertEqual({item["status"] for item in report["failed_or_incomplete_gates"]}, {"not_measured", "inconclusive"})

    def test_missing_unexpected_or_tampered_case_fails_closed(self):
        manifest = _manifest()
        reports = [_report(manifest, case_id) for case_id in EXPECTED_CASE_IDS]
        with self.assertRaisesRegex(CampaignIntegrityError, "exactly_30"):
            evaluate_offline_campaign(manifest, reports[:-1])
        tampered = copy.deepcopy(reports)
        tampered[0]["gates"]["geometry"]["status"] = "fail"
        with self.assertRaisesRegex(CampaignIntegrityError, "seal_invalid"):
            evaluate_offline_campaign(manifest, tampered)
        unexpected = copy.deepcopy(reports)
        unexpected[0] = _report(manifest, EXPECTED_CASE_IDS[0])
        unexpected[0]["case_id"] = "made-up-case"
        with self.assertRaisesRegex(CampaignIntegrityError, "unexpected_or_duplicate"):
            evaluate_offline_campaign(manifest, unexpected)

    def test_asset_and_gate_integrity_are_hash_bound(self):
        manifest = _manifest()
        reports = [_report(manifest, case_id) for case_id in EXPECTED_CASE_IDS]
        bad = copy.deepcopy(reports)
        bad[0]["asset"]["sha256"] = _asset_hash("different")
        bad[0] = seal_case_report(bad[0])
        with self.assertRaisesRegex(CampaignIntegrityError, "case_asset_hash_mismatch"):
            evaluate_offline_campaign(manifest, bad)
        bad = copy.deepcopy(reports)
        bad[0]["gates"]["uv"]["asset_sha256"] = _asset_hash("different")
        bad[0] = seal_case_report(bad[0])
        with self.assertRaisesRegex(CampaignIntegrityError, "gate_asset_hash_mismatch"):
            evaluate_offline_campaign(manifest, bad)


if __name__ == "__main__":
    unittest.main()
