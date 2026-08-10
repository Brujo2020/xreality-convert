import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from offline_campaign import EXPECTED_CASE_IDS, REQUIRED_GATES, build_campaign_manifest, seal_case_report
from offline_campaign_repository import (
    CampaignRepositoryError,
    finalize_campaign_repository,
    load_case_report,
    seal_campaign_manifest_in_repository,
    seal_case_report_in_repository,
    verify_finalized_campaign,
)


def _asset_hash(case_id):
    return "sha256:" + hashlib.sha256(case_id.encode("utf-8")).hexdigest()


def _manifest(campaign_id="buffalo-local-acceptance-v1"):
    return build_campaign_manifest(campaign_id, {case_id: _asset_hash(case_id) for case_id in EXPECTED_CASE_IDS})


def _report(manifest, case_id):
    asset_hash = next(case["asset"]["sha256"] for case in manifest["cases"] if case["case_id"] == case_id)
    return seal_case_report({
        "schema_version": 1,
        "campaign_id": manifest["campaign_id"],
        "case_id": case_id,
        "execution": {"offline": True, "network_allowed": False},
        "asset": {"sha256": asset_hash},
        "gates": {
            gate: {"status": "pass", "evidence_class": "measured", "asset_sha256": asset_hash}
            for gate in REQUIRED_GATES
        },
        "metrics": {
            "latency_seconds": {"status": "measured", "value": 1.25},
            "peak_memory_bytes": {"status": "measured", "value": 4096},
        },
    })


class OfflineCampaignRepositoryTests(unittest.TestCase):
    def _create(self, root, campaign_id="buffalo-local-acceptance-v1"):
        manifest = _manifest(campaign_id)
        return seal_campaign_manifest_in_repository(repository_root=root, manifest=manifest)

    def _fill(self, root, manifest, *, count=30):
        for case_id in EXPECTED_CASE_IDS[:count]:
            seal_case_report_in_repository(
                repository_root=root, campaign_id=manifest["campaign_id"], report=_report(manifest, case_id),
            )

    def test_seals_exact_campaign_then_recomputes_immutable_30_report_final(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self._create(root)
            self._fill(root, manifest)
            final = finalize_campaign_repository(repository_root=root, campaign_id=manifest["campaign_id"])
            self.assertEqual(final["report_count"], 30)
            self.assertEqual(final["aggregate"]["case_count"], 30)
            self.assertTrue(final["aggregate"]["passed"])
            self.assertEqual(final, verify_finalized_campaign(repository_root=root, campaign_id=manifest["campaign_id"]))
            self.assertEqual(
                (root / "campaigns" / manifest["campaign_id"] / "final.json").stat().st_mode & 0o222,
                0,
            )

    def test_missing_and_duplicate_reports_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self._create(root)
            self._fill(root, manifest, count=29)
            with self.assertRaisesRegex(CampaignRepositoryError, "report_missing"):
                finalize_campaign_repository(repository_root=root, campaign_id=manifest["campaign_id"])
            case_id = EXPECTED_CASE_IDS[0]
            with self.assertRaisesRegex(CampaignRepositoryError, "duplicate_case_report"):
                seal_case_report_in_repository(
                    repository_root=root, campaign_id=manifest["campaign_id"], report=_report(manifest, case_id),
                )

    def test_tampered_or_unsealed_persisted_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self._create(root)
            case_id = EXPECTED_CASE_IDS[0]
            seal_case_report_in_repository(
                repository_root=root, campaign_id=manifest["campaign_id"], report=_report(manifest, case_id),
            )
            report_path = root / "campaigns" / manifest["campaign_id"] / "reports" / f"{case_id}.json"
            report_path.chmod(0o600)
            report_path.write_text('{"changed":true}', encoding="utf-8")
            with self.assertRaisesRegex(CampaignRepositoryError, "not_sealed"):
                load_case_report(repository_root=root, campaign_id=manifest["campaign_id"], case_id=case_id)

    def test_cross_campaign_report_and_symlink_namespace_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self._create(root, "buffalo-local-acceptance-v1")
            second = self._create(root, "buffalo-local-acceptance-v2")
            with self.assertRaisesRegex(CampaignRepositoryError, "cross_campaign"):
                seal_case_report_in_repository(
                    repository_root=root, campaign_id=second["campaign_id"], report=_report(first, EXPECTED_CASE_IDS[0]),
                )
            reports = root / "campaigns" / first["campaign_id"] / "reports"
            reports.symlink_to(root)
            with self.assertRaisesRegex(CampaignRepositoryError, "path_unsafe"):
                seal_case_report_in_repository(
                    repository_root=root, campaign_id=first["campaign_id"], report=_report(first, EXPECTED_CASE_IDS[0]),
                )

    def test_invalid_campaign_identifier_prevents_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _manifest()
            malicious = copy.deepcopy(manifest)
            malicious["campaign_id"] = "../escape"
            # Its original manifest seal is now invalid and must be rejected
            # before it can select a managed directory.
            with self.assertRaisesRegex(CampaignRepositoryError, "manifest_seal_invalid"):
                seal_campaign_manifest_in_repository(repository_root=root, manifest=malicious)


if __name__ == "__main__":
    unittest.main()
