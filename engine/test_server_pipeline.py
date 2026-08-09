import asyncio
import inspect
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

import server


class GetPipelineTests(unittest.TestCase):
    def tearDown(self):
        server.shape_pipeline = None
        server.load_error = None
        server.m5_optimizer = None

    def test_loads_mlx_pipeline_with_its_native_contract(self):
        pipeline = object()
        shape_pipeline = mock.Mock()
        shape_pipeline.from_pretrained.return_value = pipeline

        pipeline_module = types.ModuleType("hy3dshape.hy3dshape.pipeline_mlx")
        pipeline_module.ShapePipeline = shape_pipeline
        modules = {
            "hy3dshape": types.ModuleType("hy3dshape"),
            "hy3dshape.hy3dshape": types.ModuleType("hy3dshape.hy3dshape"),
            "hy3dshape.hy3dshape.pipeline_mlx": pipeline_module,
        }

        server.m5_optimizer = object()
        with mock.patch.dict(sys.modules, modules), mock.patch.object(
            server, "patch_mlx_runtime"
        ):
            loaded = server.get_pipeline()

        self.assertIs(loaded, pipeline)
        shape_pipeline.from_pretrained.assert_called_once_with(
            "dgrauet/hunyuan3d-2.1-mlx"
        )

    @unittest.skipUnless(
        os.environ.get("XREALITY_ENABLE_MLX_INTEGRATION_TESTS") == "1",
        "requires a real Apple Metal device; set XREALITY_ENABLE_MLX_INTEGRATION_TESTS=1",
    )
    def test_bundled_shape_runtime_is_sequential_and_reports_progress(self):
        from hy3dshape.hy3dshape.pipeline_mlx import ShapePipeline

        constructor = inspect.signature(ShapePipeline.__init__).parameters
        generation = inspect.signature(ShapePipeline.__call__).parameters

        self.assertIn("dit_loader", constructor)
        self.assertIn("vae_loader", constructor)
        self.assertIn("progress_callback", generation)
        self.assertEqual(server.ENGINE_VERSION, "20")

    def test_reference_padding_matches_hunyuan_border_ratio(self):
        image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((40, 30, 59, 69), fill=(180, 90, 30, 255))

        prepared = server.prepare_reference_image(image, "animal", "keep", 0.15)

        self.assertEqual(prepared.size, (47, 47))

    def test_generation_preflight_can_skip_preview_and_expensive_background_removal(self):
        image = Image.new("RGB", (1024, 1024), "white")
        ImageDraw.Draw(image).rectangle((220, 220, 804, 804), fill=(20, 30, 40))

        with mock.patch.object(server, "prepare_reference_image") as prepare:
            report = server.analyze_image(image, "product", "auto", include_preview=False)

        self.assertEqual(report["status"], "Óptima")
        self.assertNotIn("preview_base64", report)
        prepare.assert_not_called()

    def test_artifact_seal_records_size_and_sha256(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.glb"
            path.write_bytes(b"sealed-asset")

            report = server.seal_artifact(path)

        self.assertEqual(report["bytes"], 12)
        self.assertEqual(len(report["sha256"]), 64)

    def test_status_exposes_control_plane_without_leaking_ledger_object(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = server.JobLedger(directory, "c" * 32)
            server.job_ledgers["c" * 32] = ledger
            server.jobs["c" * 32] = {"status": "queued"}
            try:
                report = server.status("c" * 32)
            finally:
                server.job_ledgers.pop("c" * 32, None)
                server.jobs.pop("c" * 32, None)

        self.assertEqual(report["control_plane"]["state"]["state"], "DRAFT")
        self.assertIn("journal.jsonl", report["control_plane"]["journal_path"])

    def test_open_product_is_attention_for_xr_but_rejected_for_master(self):
        import trimesh

        mesh = trimesh.creation.icosphere(subdivisions=3)
        mesh.update_faces([True] * (len(mesh.faces) - 1) + [False])
        mesh.remove_unreferenced_vertices()
        request_xr = server.GenerateRequest(
            image_base64="a" * 32,
            category="product",
            profile="xreal",
            target_faces=50000,
        )
        request_master = request_xr.model_copy(update={"profile": "maxquality"})

        xr_quality = server.compute_quality(
            mesh,
            "product",
            request_xr,
            len(mesh.faces),
            len(mesh.faces),
            server.plan_asset(category="product", profile="xreal"),
        )
        master_quality = server.compute_quality(
            mesh,
            "product",
            request_master,
            len(mesh.faces),
            len(mesh.faces),
            server.plan_asset(category="product", profile="maxquality"),
        )

        self.assertFalse(xr_quality["watertight"])
        self.assertEqual(xr_quality["level"], "atencion")
        self.assertIn("STL permanece bloqueado", " ".join(xr_quality["reasons"]))
        self.assertEqual(master_quality["level"], "critico")
        self.assertIn("nivel maestro", " ".join(master_quality["reasons"]))

        self.assertTrue(server.admit_renderable_glb_fallback(master_quality))
        self.assertEqual(master_quality["contract_level"], "critico")
        self.assertEqual(master_quality["level"], "atencion")
        self.assertFalse(master_quality["master_promotion_passed"])
        self.assertIn("no STL", " ".join(master_quality["reasons"]))

    def test_open_assembly_is_not_penalized_as_a_broken_solid(self):
        import trimesh

        mesh = trimesh.creation.icosphere(subdivisions=4)
        mesh.update_faces([True] * (len(mesh.faces) - 1) + [False])
        mesh.remove_unreferenced_vertices()
        request = server.GenerateRequest(
            image_base64="a" * 32,
            category="truck",
            profile="xreal",
            target_faces=50000,
        )
        quality = server.compute_quality(
            mesh,
            "truck",
            request,
            len(mesh.faces),
            len(mesh.faces),
            server.plan_asset(category="truck", profile="xreal"),
        )

        self.assertFalse(quality["watertight"])
        self.assertEqual(quality["level"], "listo")
        self.assertNotIn("watertight", " ".join(quality["reasons"]))

    def test_texture_flow_promotes_only_visually_accepted_native_paint(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.glb"
            mesh = mock.Mock()
            mesh.export.side_effect = lambda path: Path(path).write_bytes(b"shape")
            service = mock.Mock()

            def write_paint(**kwargs):
                Path(kwargs["output_glb_path"]).write_bytes(b"paint")
                return {"passed": True}

            service.run.side_effect = write_paint
            visual_report = {"gate": {"passed": True}}
            material_report = {"passed": True, "premium_ready": True}
            with mock.patch.object(server, "PaintService", return_value=service), mock.patch.object(
                server, "validate_native_paint_glb", return_value=visual_report
            ), mock.patch.object(
                server, "apply_material_features", return_value={"applied": False, "extensions": []}
            ), mock.patch.object(
                server, "validate_material_contract", return_value=material_report
            ):
                report, shape_path = server.apply_texture_to_mesh(
                    mesh, "reference.png", 2048, output, category="product", profile="mobile"
                )

            self.assertEqual(output.read_bytes(), b"paint")
            self.assertEqual(report["visual_fidelity"], visual_report)
            self.assertTrue(Path(shape_path).is_file())
            service.run.assert_called_once()

    def test_texture_flow_does_not_promote_rejected_native_paint(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.glb"
            mesh = mock.Mock()
            mesh.export.side_effect = lambda path: Path(path).write_bytes(b"shape")
            service = mock.Mock()
            def write_attention_paint(**kwargs):
                Path(kwargs["output_glb_path"]).write_bytes(b"paint")
                return {"passed": True}
            service.run.side_effect = write_attention_paint
            with mock.patch.object(server, "PaintService", return_value=service), mock.patch.object(
                server,
                "validate_native_paint_glb",
                return_value={"gate": {"passed": False, "reasons": ["paint_loss"]}},
            ), mock.patch.object(
                server, "apply_material_features", return_value={"applied": False, "extensions": []}
            ), mock.patch.object(
                server, "validate_material_contract", return_value={"passed": True, "premium_ready": False}
            ):
                report, _ = server.apply_texture_to_mesh(
                    mesh, "reference.png", 2048, output, category="product", profile="mobile"
                )

            self.assertEqual(output.read_bytes(), b"paint")
            self.assertEqual(report["backend"], "hunyuan-fast")
            self.assertTrue(report["degraded"])
            self.assertEqual(report["visual_attention"], ["paint_loss"])

    def test_texture_flow_can_use_isolated_agentic_quality_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.glb"
            mesh = mock.Mock()
            mesh.export.side_effect = lambda path: Path(path).write_bytes(b"shape")
            service = mock.Mock()

            def write_agentic(**kwargs):
                Path(kwargs["output_glb_path"]).write_bytes(b"agentic")
                return {"passed": True, "backend": "agenticvibes-mlx-quality"}

            service.run.side_effect = write_agentic
            with mock.patch.object(
                server, "AgenticPaintService", return_value=service
            ), mock.patch.object(server, "validate_native_paint_glb") as native_gate:
                with mock.patch.object(
                    server, "apply_material_features", return_value={"applied": True, "extensions": ["KHR_materials_sheen"]}
                ), mock.patch.object(
                    server, "validate_material_contract", return_value={"passed": True, "premium_ready": False}
                ):
                    report, shape_path = server.apply_texture_to_mesh(
                        mesh,
                        "reference.png",
                        2048,
                        output,
                        category="animal",
                        paint_backend="agentic",
                    )

            self.assertEqual(output.read_bytes(), b"agentic")
            self.assertEqual(report["backend"], "agenticvibes-mlx-quality")
            self.assertTrue(Path(shape_path).is_file())
            native_gate.assert_not_called()
            service.run.assert_called_once_with(
                mesh_path=Path(directory) / "result-shape.glb",
                image_path="reference.png",
                output_glb_path=output,
                steps=4,
                texture_size=1024,
                seed=42,
            )

    def test_agentic_failure_recovers_with_fast_paint_and_reports_degradation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.glb"
            mesh = mock.Mock()
            mesh.export.side_effect = lambda path: Path(path).write_bytes(b"shape")
            fast_service = mock.Mock()
            def write_fast(**kwargs):
                Path(kwargs["output_glb_path"]).write_bytes(b"fast")
                return {"passed": True}
            fast_service.run.side_effect = write_fast
            with mock.patch.object(
                server.AgenticPaintService, "run", side_effect=RuntimeError("cache incomplete")
            ), mock.patch.object(
                server, "PaintService", return_value=fast_service
            ), mock.patch.object(
                server, "validate_native_paint_glb", return_value={"gate": {"passed": True}}
            ), mock.patch.object(
                server, "apply_material_features", return_value={"applied": False, "extensions": []}
            ), mock.patch.object(
                server, "validate_material_contract", return_value={"passed": True, "premium_ready": False}
            ):
                report, _ = server.apply_texture_to_mesh(
                    mesh, "reference.png", 1024, output, category="industrial",
                    paint_backend="agentic", profile="xreal"
                )

            self.assertEqual(output.read_bytes(), b"fast")
            self.assertTrue(report["passed"])
            self.assertTrue(report["degraded"])
            self.assertEqual(report["backend"], "hunyuan-fast-recovery")
            self.assertEqual(report["fallback_chain"][0]["backend"], "agentic")

    def test_both_paint_failures_deliver_geometry_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.glb"
            mesh = mock.Mock()
            mesh.export.side_effect = lambda path: Path(path).write_bytes(b"shape")
            fast_service = mock.Mock()
            fast_service.run.side_effect = RuntimeError("fast unavailable")
            with mock.patch.object(
                server.AgenticPaintService, "run", side_effect=RuntimeError("agentic unavailable")
            ), mock.patch.object(server, "PaintService", return_value=fast_service):
                report, shape_path = server.apply_texture_to_mesh(
                    mesh, "reference.png", 1024, output, category="industrial",
                    paint_backend="agentic", profile="xreal"
                )

            self.assertEqual(output.read_bytes(), b"shape")
            self.assertEqual(Path(shape_path).read_bytes(), b"shape")
            self.assertFalse(report["passed"])
            self.assertTrue(report["degraded"])
            self.assertEqual(report["backend"], "geometry-checkpoint")
            self.assertEqual(len(report["fallback_chain"]), 2)

    def test_material_validation_exception_delivers_geometry_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.glb"
            mesh = mock.Mock()
            mesh.export.side_effect = lambda path: Path(path).write_bytes(b"shape")
            fast_service = mock.Mock()
            def write_fast(**kwargs):
                Path(kwargs["output_glb_path"]).write_bytes(b"fast")
                return {"passed": True}
            fast_service.run.side_effect = write_fast
            with mock.patch.object(
                server, "PaintService", return_value=fast_service
            ), mock.patch.object(
                server, "validate_native_paint_glb", return_value={"gate": {"passed": True}}
            ), mock.patch.object(
                server, "apply_material_features", side_effect=RuntimeError("material crash")
            ):
                report, _ = server.apply_texture_to_mesh(
                    mesh, "reference.png", 1024, output, category="product",
                    paint_backend="fast", profile="mobile"
                )

            self.assertEqual(output.read_bytes(), b"shape")
            self.assertEqual(report["backend"], "geometry-checkpoint")
            self.assertIn("material_validation_error", report["fallback_chain"][-1]["error"])

    def test_release_shape_pipeline_clears_global_and_mlx_cache(self):
        pipeline = object()
        optimizer = mock.Mock()
        server.shape_pipeline = pipeline
        server.m5_optimizer = optimizer

        server.release_shape_pipeline(pipeline)

        self.assertIsNone(server.shape_pipeline)
        optimizer.clear_cache.assert_called_once_with()

    def test_settle_shape_memory_collects_after_caller_drops_reference(self):
        optimizer = mock.Mock()
        server.m5_optimizer = optimizer
        with mock.patch.object(server.gc, "collect") as collect:
            server.settle_shape_memory()
        collect.assert_called_once_with()
        optimizer.clear_cache.assert_called_once_with()


class EngineTokenTests(unittest.TestCase):
    def setUp(self):
        self.previous = server.ENGINE_TOKEN
        server.ENGINE_TOKEN = "test-token"

    def tearDown(self):
        server.ENGINE_TOKEN = self.previous

    def test_health_remains_available_for_process_discovery(self):
        request = types.SimpleNamespace(url=types.SimpleNamespace(path="/health"), headers={})
        next_handler = mock.AsyncMock(return_value="ok")

        response = asyncio.run(server.require_engine_token(request, next_handler))

        self.assertEqual(response, "ok")
        next_handler.assert_awaited_once_with(request)

    def test_engine_endpoints_require_local_token(self):
        request = types.SimpleNamespace(url=types.SimpleNamespace(path="/analyze"), headers={})
        response = asyncio.run(server.require_engine_token(request, mock.AsyncMock()))

        self.assertEqual(response.status_code, 401)

    def test_valid_token_reaches_endpoint_validation(self):
        request = types.SimpleNamespace(
            url=types.SimpleNamespace(path="/analyze"),
            headers={"x-xreality-engine-token": "test-token"},
        )
        next_handler = mock.AsyncMock(return_value="accepted")
        response = asyncio.run(server.require_engine_token(request, next_handler))

        self.assertEqual(response, "accepted")


class GeometryCheckpointRecoveryTests(unittest.TestCase):
    def test_unexpected_post_geometry_error_returns_attention_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs_dir = Path(directory) / "jobs"
            reports_dir = jobs_dir / "reports"
            jobs_dir.mkdir()
            (jobs_dir / "job-shape.glb").write_bytes(b"validated-geometry")
            job = {"status": "running"}
            with mock.patch.object(server, "JOBS_DIR", jobs_dir), mock.patch.object(
                server, "REPORTS_DIR", reports_dir
            ):
                recovered = server.recover_from_geometry_checkpoint(
                    "job", job, RuntimeError("unexpected paint failure"), time.monotonic(),
                    {"quality_tier": "premium"}
                )

            self.assertTrue(recovered)
            self.assertEqual((jobs_dir / "job.glb").read_bytes(), b"validated-geometry")
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["quality_level"], "atencion")
            self.assertFalse(job["texture_applied"])


if __name__ == "__main__":
    unittest.main()
