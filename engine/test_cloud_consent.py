import json
import tempfile
import unittest
from pathlib import Path

from cloud_consent import (
    CloudConsentError,
    create_consent,
    engage_kill_switch,
    reconcile_budget,
    reserve_budget,
    verify_consent,
)


ASSET = "sha256:" + "a" * 64
PROVIDERS = ("meshy", "local_proxy")


class CloudConsentTests(unittest.TestCase):
    def _consent(self, job: Path, *, expiry: float = 2_000.0):
        return create_consent(
            job_dir=job, asset_sha256=ASSET, provider="meshy", operation="texture_refine",
            max_cost_micros=2_000_000, currency="USD", expires_at=expiry,
            allowed_providers=PROVIDERS, clock=lambda: 1_000.0,
        )

    def test_consent_is_hash_bound_immutable_and_exactly_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / "job"
            job.mkdir()
            consent = self._consent(job)
            self.assertTrue(consent["record_id"].startswith("sha256:"))
            path = next((job / "cloud-consents").glob("*.json"))
            self.assertFalse(path.stat().st_mode & 0o222)
            verified = verify_consent(
                job_dir=job, consent_id=consent["record_id"], asset_sha256=ASSET,
                provider="meshy", operation="texture_refine", allowed_providers=PROVIDERS,
                now=1_100.0,
            )
            self.assertEqual(verified["max_cost_micros"], 2_000_000)
            with self.assertRaisesRegex(CloudConsentError, "consent_asset_mismatch"):
                verify_consent(job_dir=job, consent_id=consent["record_id"], asset_sha256="b" * 64,
                               provider="meshy", operation="texture_refine", allowed_providers=PROVIDERS, now=1_100.0)
            with self.assertRaisesRegex(CloudConsentError, "consent_provider_mismatch"):
                verify_consent(job_dir=job, consent_id=consent["record_id"], asset_sha256=ASSET,
                               provider="local_proxy", operation="texture_refine", allowed_providers=PROVIDERS, now=1_100.0)

    def test_allowlist_expiry_and_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / "job"
            job.mkdir()
            with self.assertRaisesRegex(CloudConsentError, "provider_not_allowlisted"):
                create_consent(job_dir=job, asset_sha256=ASSET, provider="unknown", operation="shape",
                               max_cost_micros=1, currency="USD", expires_at=2_000.0,
                               allowed_providers=PROVIDERS, clock=lambda: 1_000.0)
            consent = self._consent(job)
            with self.assertRaisesRegex(CloudConsentError, "consent_expired"):
                verify_consent(job_dir=job, consent_id=consent["record_id"], asset_sha256=ASSET,
                               provider="meshy", operation="texture_refine", allowed_providers=PROVIDERS, now=2_000.0)
            path = next((job / "cloud-consents").glob("*.json"))
            path.chmod(0o600)
            data = json.loads(path.read_text())
            data["max_cost_micros"] = 999_999_999
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(CloudConsentError, "consent_missing_or_invalid"):
                verify_consent(job_dir=job, consent_id=consent["record_id"], asset_sha256=ASSET,
                               provider="meshy", operation="texture_refine", allowed_providers=PROVIDERS, now=1_100.0)

    def test_reservation_accounting_reconciliation_and_overspend_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / "job"
            job.mkdir()
            consent = self._consent(job)
            reserved = reserve_budget(job_dir=job, consent_id=consent["record_id"], asset_sha256=ASSET,
                                      provider="meshy", operation="texture_refine", allowed_providers=PROVIDERS,
                                      activity_id="request-1", amount_micros=1_500_000, clock=lambda: 1_100.0)
            self.assertEqual(reserved["remaining_micros"], 500_000)
            with self.assertRaisesRegex(CloudConsentError, "cloud_budget_exceeded"):
                reserve_budget(job_dir=job, consent_id=consent["record_id"], asset_sha256=ASSET,
                               provider="meshy", operation="texture_refine", allowed_providers=PROVIDERS,
                               activity_id="request-2", amount_micros=500_001, clock=lambda: 1_100.0)
            closed = reconcile_budget(job_dir=job, consent_id=consent["record_id"], activity_id="request-1",
                                      actual_cost_micros=1_000_000, clock=lambda: 1_200.0)
            self.assertEqual(closed["remaining_micros"], 1_000_000)
            with self.assertRaisesRegex(CloudConsentError, "cloud_reservation_missing_or_closed"):
                reconcile_budget(job_dir=job, consent_id=consent["record_id"], activity_id="request-1",
                                 actual_cost_micros=1, clock=lambda: 1_201.0)
            reserve_budget(job_dir=job, consent_id=consent["record_id"], asset_sha256=ASSET,
                           provider="meshy", operation="texture_refine", allowed_providers=PROVIDERS,
                           activity_id="request-2", amount_micros=500_000, clock=lambda: 1_300.0)
            with self.assertRaisesRegex(CloudConsentError, "actual_cost_exceeds_reserved_budget"):
                reconcile_budget(job_dir=job, consent_id=consent["record_id"], activity_id="request-2",
                                 actual_cost_micros=500_001, clock=lambda: 1_301.0)
            audit = list((job / "cloud-audit").glob("*.json"))
            self.assertEqual(len(audit), 3)
            self.assertTrue(all(not item.stat().st_mode & 0o222 for item in audit))

    def test_kill_switch_is_irreversible_and_blocks_future_billing(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / "job"
            job.mkdir()
            consent = self._consent(job)
            killed = engage_kill_switch(job_dir=job, reason="operator_stop", clock=lambda: 1_100.0)
            self.assertEqual(killed["effect"], "all_future_cloud_reservations_denied")
            with self.assertRaisesRegex(CloudConsentError, "cloud_kill_switch_engaged"):
                reserve_budget(job_dir=job, consent_id=consent["record_id"], asset_sha256=ASSET,
                               provider="meshy", operation="texture_refine", allowed_providers=PROVIDERS,
                               activity_id="request-1", amount_micros=1, clock=lambda: 1_101.0)
            with self.assertRaisesRegex(CloudConsentError, "cloud_kill_switch_already_engaged"):
                engage_kill_switch(job_dir=job, reason="operator_stop", clock=lambda: 1_102.0)


if __name__ == "__main__":
    unittest.main()
