import os
import shutil
import tempfile
import unittest
from pathlib import Path
from invencible_pipeline import InvenciblePipeline, StageStatus


class TestInvenciblePipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.job_dir = Path(self.temp_dir)
        self.mock_image = self.job_dir / "input.jpg"
        self.mock_image.touch()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_pipeline_execution(self):
        pipeline = InvenciblePipeline(self.job_dir)
        manifest = pipeline.run(self.mock_image)
        self.assertEqual(manifest.final_status, "passed")
        self.assertEqual(len(manifest.stages), 10)
        self.assertTrue((self.job_dir / "pipeline_manifest.json").exists())

    def test_checkpoint_roundtrip(self):
        pipeline = InvenciblePipeline(self.job_dir)

        res = pipeline._run_stage("intake", pipeline._stage_intake, image_path=self.mock_image)
        self.assertEqual(res.status, StageStatus.PASSED)

        chk = pipeline._load_checkpoint("intake")
        self.assertIsNotNone(chk)
        self.assertEqual(chk.stage_name, "intake")
        self.assertEqual(chk.status, StageStatus.PASSED)

    def test_stage_failure_handling(self):
        pipeline = InvenciblePipeline(self.job_dir)

        def failing_intake(**kwargs):
            raise ValueError("Simulated failure")

        pipeline._stage_intake = failing_intake
        manifest = pipeline.run(self.mock_image)

        self.assertEqual(manifest.final_status, "rejected")
        self.assertEqual(len(manifest.stages), 1)
        self.assertEqual(manifest.stages[0].status, StageStatus.REJECTED)

    def test_graceful_degradation(self):
        pipeline = InvenciblePipeline(self.job_dir)

        def failing_flexicubes(**kwargs):
            raise ValueError("FlexiCubes failed")

        pipeline._stage_mesh_extraction = failing_flexicubes

        manifest = pipeline.run(self.mock_image)
        self.assertEqual(manifest.final_status, "passed")

        mesh_ext_stage = next(s for s in manifest.stages if s.stage_name == "mesh_extraction")
        self.assertEqual(mesh_ext_stage.status, StageStatus.REJECTED)

    def test_manifest_structure(self):
        pipeline = InvenciblePipeline(self.job_dir)
        manifest = pipeline.run(self.mock_image)

        self.assertEqual(manifest.pipeline_version, "INVENCIBLE_2027_v1")
        self.assertEqual(manifest.job_id, self.job_dir.name)
        self.assertIsNotNone(manifest.master_glb_path)
        self.assertIsNotNone(manifest.asset_graph_path)

    def test_resume_from_checkpoint(self):
        pipeline1 = InvenciblePipeline(self.job_dir)

        def failing_repair(**kwargs):
            raise ValueError("Repair fail")
        pipeline1._stage_mesh_repair = failing_repair

        manifest1 = pipeline1.run(self.mock_image)
        self.assertEqual(manifest1.final_status, "rejected")

        stages_passed = [s.stage_name for s in manifest1.stages if s.status == StageStatus.PASSED]
        self.assertIn("intake", stages_passed)
        self.assertIn("shape", stages_passed)

        pipeline2 = InvenciblePipeline(self.job_dir)
        manifest2 = pipeline2.run(self.mock_image)
        self.assertEqual(manifest2.final_status, "passed")

    def test_progress_callback(self):
        calls = []

        def progress_cb(current, total, name, percent):
            calls.append((current, total, name, percent))

        pipeline = InvenciblePipeline(self.job_dir, progress_callback=progress_cb)
        pipeline.run(self.mock_image)

        self.assertEqual(len(calls), 10)
        self.assertEqual(calls[0], (1, 10, "intake", 1.0))
        self.assertEqual(calls[-1], (10, 10, "manifest", 1.0))


if __name__ == "__main__":
    unittest.main()
