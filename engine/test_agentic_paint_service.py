import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agentic_paint_service
from agentic_paint_service import admit_agentic


class AgenticAdmissionTests(unittest.TestCase):
    def test_accepts_healthy_24gb_machine(self):
        report = admit_agentic(
            {
                "physical_gb": 24.0,
                "free_percent": 52.0,
                "swap_used_mb": 0.0,
                "swap_free_mb": 4096.0,
            }
        )
        self.assertTrue(report["passed"])

    def test_dynamic_swap_free_is_not_treated_as_fixed_capacity(self):
        report = admit_agentic(
            {
                "physical_gb": 24.0,
                "free_percent": 67.0,
                "swap_used_mb": 10000.0,
                "swap_free_mb": 954.0,
            }
        )
        self.assertTrue(report["passed"])
        self.assertNotIn("swap_headroom_below_2gb", report["reasons"])

    def test_rejects_memory_pressure_even_with_enough_physical_memory(self):
        report = admit_agentic(
            {
                "physical_gb": 48.0,
                "free_percent": 20.0,
                "swap_used_mb": 0.0,
                "swap_free_mb": 8192.0,
            }
        )
        self.assertFalse(report["passed"])
        self.assertIn("memory_pressure_too_high", report["reasons"])

    def test_uses_inference_complete_cache_when_only_metadata_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            cached = Path(directory)
            (cached / "unet.npz").write_bytes(b"unet")
            (cached / "vae.npz").write_bytes(b"vae")
            with mock.patch.object(
                agentic_paint_service, "snapshot_download", side_effect=RuntimeError("missing .gitattributes")
            ), mock.patch.object(
                agentic_paint_service, "_cached_revision_path", return_value=cached
            ):
                resolved = agentic_paint_service._snapshot(
                    "AgenticVibes/hunyuan3d-2.1-mlx",
                    "revision",
                    required_files=("unet.npz", "vae.npz"),
                )
        self.assertEqual(resolved, cached)


if __name__ == "__main__":
    unittest.main()
