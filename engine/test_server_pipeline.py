import asyncio
import inspect
import json
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
from buffalo_runtime import canonical_json
from master_promotion_service import DEFAULT_GATE_PRODUCERS
from review_policy import (
    DEFAULT_REVIEW_POLICY,
    REVIEW_POLICY_KIND,
    REVIEW_POLICY_SCHEMA_VERSION,
    REVIEWER_REGISTRY_KIND,
    REVIEWER_REGISTRY_SCHEMA_VERSION,
)
from review_gate_evidence import (
    GATE_EVIDENCE_SCHEMA_VERSION,
    GATE_SOURCE_CLASS,
    GATE_SOURCE_KIND,
    seal_gate_result,
)


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

    def test_startup_recovery_exposes_interrupted_job_without_replaying_ml(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = server.JobLedger(directory, "e" * 32)
            ledger.transition("SEALED", "test")
            original_jobs_dir = server.JOBS_DIR
            try:
                server.JOBS_DIR = Path(directory)
                asyncio.run(server.recover_control_plane_after_restart())
                self.assertEqual(server.job_ledgers["e" * 32].state, "CANCELLED")
                self.assertEqual(server.jobs["e" * 32]["status"], "interrupted")
            finally:
                server.JOBS_DIR = original_jobs_dir
                server.jobs.pop("e" * 32, None)
                server.job_ledgers.pop("e" * 32, None)

    def test_retry_rebuilds_only_a_restart_recovered_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = "f" * 32
            ledger = server.JobLedger(root, source)
            ledger.seal({"job_id": source}, {"input": {}}, {
                "category": "product", "profile": "mobile", "steps": 10,
                "octree_resolution": 96, "texture": False,
            })
            ledger.transition("PREFLIGHTED", "test")
            ledger.transition("RUNNING_STAGE", "test")
            server.recover_interrupted_ledgers(root)
            Image.new("RGB", (32, 32), "blue").save(root / f"{source}.png")
            original_jobs_dir = server.JOBS_DIR
            try:
                server.JOBS_DIR = root
                request = server.build_explicit_retry_request(source)
            finally:
                server.JOBS_DIR = original_jobs_dir
        self.assertEqual(request.category, "product")
        self.assertFalse(request.texture)

    def test_asset_plan_compiles_to_a_stable_semantic_graph(self):
        plan = server.plan_asset(category="forklift", profile="xreal")
        graph = server.compile_semantic_graph(plan["semantic_contract"])
        self.assertTrue(graph["graph_id"].startswith("sha256:"))
        self.assertGreater(len(graph["nodes"]), 2)

    def test_runtime_certification_rejects_unmanaged_glb_before_certifying(self):
        response = server.certify_runtime(server.RuntimeCertificationRequest(
            glb_path="/tmp/not-managed.glb", target="mobile"
        ))
        self.assertFalse(response["ok"])
        self.assertIn("administrados", response["error"])

    def test_replace_material_uses_new_managed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "master.glb"
            source.write_bytes(b"glTF")
            original_jobs_dir = server.JOBS_DIR
            try:
                server.JOBS_DIR = root
                with mock.patch.object(server, "validate_glb_container"), mock.patch.object(
                    server, "execute_replace_material", return_value={"edit_type": "replace_material"}
                ) as execute:
                    response = server.edit_replace_material(server.ReplaceMaterialEditRequest(
                        source_glb_path=str(source), delta={"edit_type": "replace_material"}
                    ))
            finally:
                server.JOBS_DIR = original_jobs_dir
        self.assertTrue(response["ok"])
        self.assertNotEqual(execute.call_args.args[0], execute.call_args.args[1])

    def test_derivative_manifest_requires_managed_artifacts(self):
        response = server.seal_derivative(server.DerivativeManifestRequest(
            master_glb_path="/tmp/master.glb", output_path="/tmp/output.glb", target="mobile",
            topology_changed=False, target_certificate={"status": "pass"},
        ))
        self.assertFalse(response["ok"])
        self.assertIn("administrados", response["error"])

    def test_blender_validation_requires_a_sealed_job(self):
        response = server.validate_blender_canonically(server.BlenderValidationRequest(
            job_id="a" * 32, glb_path="asset.glb", projection_report_path="projection.json", output_dir="blender"
        ))
        self.assertFalse(response["ok"])
        self.assertEqual(response["promotion"], "blocked")

    def test_validation_artifacts_reject_unsealed_job(self):
        response = server.stage_validation_artifacts(server.ValidationArtifactStageRequest(
            job_id="b" * 32, glb_path="/tmp/a.glb", projection_report_path="/tmp/projection.json"
        ))
        self.assertFalse(response["ok"])
        self.assertIn("sellado", response["error"])

    def test_blender_repair_rejects_unsealed_job(self):
        response = server.repair_with_blender(server.BlenderRepairRequest(
            job_id="c" * 32, source_glb_path="asset.glb", output_glb_path="repaired.glb", operation_contract={}
        ))
        self.assertFalse(response["ok"])
        self.assertEqual(response["promotion"], "blocked")

    def test_lod_derivation_rejects_unmanaged_master(self):
        response = server.derive_lod(server.LODDerivationRequest(
            master_glb_path="/tmp/master.glb", output_name="mobile.glb", target_faces=100
        ))
        self.assertFalse(response["ok"])
        self.assertTrue(response["rebake_required"])

    def test_regional_pbr_audit_rejects_unsealed_job(self):
        response = server.audit_pbr_regions(server.RegionalPBRAuditRequest(
            job_id="d" * 32, glb_path="/tmp/master.glb", regional_map_contract={}
        ))
        self.assertFalse(response["ok"])
        self.assertIn("sellado", response["error"])

    def test_pbr_texture_audit_rejects_unsealed_job(self):
        response = server.audit_pbr_texture_maps(server.RegionalPBRAuditRequest(
            job_id="d" * 32, glb_path="/tmp/master.glb", regional_map_contract={}
        ))
        self.assertFalse(response["ok"])
        self.assertIn("sellado", response["error"])

    def test_geometry_audit_rejects_unsealed_job(self):
        response = server.audit_geometry(server.GeometryQualityRequest(
            job_id="d" * 32, glb_path="/tmp/master.glb", policy={}
        ))
        self.assertFalse(response["ok"])
        self.assertIn("sellado", response["error"])

    def test_gltf_validator_rejects_unsealed_job(self):
        response = server.validate_gltf(server.GlTFValidatorRequest(
            job_id="d" * 32, glb_path="/tmp/master.glb"
        ))
        self.assertFalse(response["ok"])
        self.assertIn("sellado", response["error"])

    def test_cloud_consent_is_disabled_without_an_operator_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_id = "e" * 32
            ledger = server.JobLedger(root, job_id)
            ledger.seal({"job_id": job_id}, {"input": {}}, {"category": "product"})
            asset = ledger.job_dir / "asset.glb"
            asset.write_bytes(b"cloud-input")
            original_jobs_dir = server.JOBS_DIR
            original_allowlist = server.CLOUD_ALLOWED_PROVIDERS
            try:
                server.JOBS_DIR = root
                server.CLOUD_ALLOWED_PROVIDERS = ()
                response = server.create_cloud_consent(server.CloudConsentRequest(
                    job_id=job_id, asset_path=str(asset), provider="meshy",
                    operation="texture_refine", max_cost_micros=0,
                    expires_at=time.time() + 60,
                ))
            finally:
                server.JOBS_DIR = original_jobs_dir
                server.CLOUD_ALLOWED_PROVIDERS = original_allowlist
                server.job_ledgers.pop(job_id, None)

        self.assertFalse(response["ok"])
        self.assertFalse(response["network_started"])
        self.assertIn("allowlist", response["error"])

    def test_master_review_cannot_activate_without_sealed_operator_configuration(self):
        original_policy = server.MASTER_REVIEW_POLICY_PATH
        original_registry = server.MASTER_REVIEWER_REGISTRY_PATH
        try:
            server.MASTER_REVIEW_POLICY_PATH = ""
            server.MASTER_REVIEWER_REGISTRY_PATH = ""
            response = server.decide_master_promotion(server.MasterPromotionRequest(
                job_id="f" * 32, asset_path="/tmp/unmanaged.glb",
                reviewer_id="td_ana", decision="approve",
            ))
        finally:
            server.MASTER_REVIEW_POLICY_PATH = original_policy
            server.MASTER_REVIEWER_REGISTRY_PATH = original_registry
        self.assertFalse(response["ok"])
        self.assertEqual(response["promotion"], "blocked")
        self.assertIn("no están configurados", response["error"])

    def test_master_review_transitions_only_a_waiting_job_with_all_sealed_evidence(self):
        import trimesh

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_id = "a1" * 16
            ledger = server.JobLedger(root, job_id)
            ledger.seal({"job_id": job_id}, {"input": {}}, {"category": "product"})
            for target in ("PREFLIGHTED", "RUNNING_STAGE", "STAGE_PASSED", "DELIVERY_CANDIDATE", "HUMAN_REVIEW_REQUIRED"):
                ledger.transition(target, "test")
            asset = ledger.job_dir / "delivery-candidate" / "asset.glb"
            asset.parent.mkdir()
            trimesh.creation.box().export(asset)
            digest = server.hashlib.sha256(asset.read_bytes()).hexdigest()
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
                source = {
                    **source_payload,
                    "source_id": "sha256:" + server.hashlib.sha256(
                        canonical_json(source_payload)
                    ).hexdigest(),
                }
                source_path = ledger.job_dir / "gate-sources" / f"{gate.lane}.json"
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.write_text(json.dumps(source), encoding="utf-8")
                source_path.chmod(0o400)
                seal_gate_result(job_dir=ledger.job_dir, asset_path=asset, lane=gate.lane, stage=gate.stage)
            policy = root / "review-policy.json"
            policy.write_text(json.dumps({
                "schema_version": REVIEW_POLICY_SCHEMA_VERSION, "kind": REVIEW_POLICY_KIND,
                "policy_id": "review_master_local_v1",
                "gates": [{"lane": gate.lane, "stage": gate.stage} for gate in DEFAULT_REVIEW_POLICY.gates],
            }), encoding="utf-8")
            registry = root / "reviewers.json"
            registry.write_text(json.dumps({
                "schema_version": REVIEWER_REGISTRY_SCHEMA_VERSION, "kind": REVIEWER_REGISTRY_KIND,
                "policy_id": "review_master_local_v1",
                "reviewers": [{"id": "td_ana", "display_name": "Ana", "roles": ["technical_director"]}],
            }), encoding="utf-8")
            policy.chmod(0o400)
            registry.chmod(0o400)
            previous_jobs, previous_policy, previous_registry = (
                server.JOBS_DIR, server.MASTER_REVIEW_POLICY_PATH, server.MASTER_REVIEWER_REGISTRY_PATH
            )
            try:
                server.JOBS_DIR = root
                server.MASTER_REVIEW_POLICY_PATH = str(policy)
                server.MASTER_REVIEWER_REGISTRY_PATH = str(registry)
                response = server.decide_master_promotion(server.MasterPromotionRequest(
                    job_id=job_id, asset_path=str(asset), reviewer_id="td_ana", decision="approve",
                ))
                final_state = server.JobLedger.load(root, job_id).state
            finally:
                server.JOBS_DIR, server.MASTER_REVIEW_POLICY_PATH, server.MASTER_REVIEWER_REGISTRY_PATH = (
                    previous_jobs, previous_policy, previous_registry
                )
                server.job_ledgers.pop(job_id, None)

        self.assertTrue(response["ok"])
        self.assertEqual(response["promotion"], "MASTER")
        self.assertEqual(final_state, "MASTER")

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

    def test_premium_texture_flow_handles_native_paint_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.glb"
            mesh = mock.Mock()
            mesh.export.side_effect = lambda path: Path(path).write_bytes(b"shape")
            service = mock.Mock()
            service.run.side_effect = lambda **kwargs: (Path(kwargs["output_glb_path"]).write_bytes(b"paint"), {"passed": True})[1]
            with mock.patch.object(server, "PaintService", return_value=service), mock.patch.object(
                server, "validate_native_paint_glb", return_value={"gate": {"passed": False, "reasons": ["palette_shift"]}}
            ) as native_gate:
                with mock.patch.object(server, "apply_material_features", return_value={"applied": True, "extensions": []}), mock.patch.object(server, "validate_material_contract", return_value={"passed": True, "premium_ready": True}):
                    report, _ = server.apply_texture_to_mesh(
                        mesh, "reference.png", 2048, output, category="animal", profile="xreal"
                    )
            self.assertEqual(output.read_bytes(), b"paint")
            self.assertEqual(report["backend"], "hunyuan-fast")
            self.assertTrue(report["degraded"])
            self.assertFalse(native_gate.call_args_list[0].kwargs["fail_closed"])

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
                texture_size=2048,
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

    def test_material_validation_warning_preserves_painted_mesh(self):
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

            self.assertEqual(output.read_bytes(), b"fast")
            self.assertTrue(report["passed"])
            self.assertTrue(report["degraded"])
            self.assertIn("material_enhancement_skipped", report["fallback_chain"][-1]["warning"])

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


class EngineHealthTests(unittest.TestCase):
    def setUp(self):
        self.previous_source = server.SOURCE
        self.previous_error = server.load_error

    def tearDown(self):
        server.SOURCE = self.previous_source
        server.load_error = self.previous_error

    def test_lazy_runtime_is_ready_before_model_is_loaded(self):
        server.SOURCE = Path(__file__).resolve().parents[1]
        server.load_error = None

        report = server.health()

        self.assertTrue(report["ready"])
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["degraded_reasons"], [])

    def test_failed_pipeline_load_is_explicitly_degraded(self):
        server.SOURCE = Path(__file__).resolve().parents[1]
        server.load_error = "missing local weight"

        report = server.health()

        self.assertFalse(report["ready"])
        self.assertEqual(report["status"], "degraded")
        self.assertEqual(report["degraded_reasons"], ["shape_pipeline_load_failed"])

    def test_missing_runtime_is_explicitly_unavailable(self):
        server.SOURCE = Path("/definitely/missing/xreality-shape-runtime")
        server.load_error = None

        report = server.health()

        self.assertFalse(report["ready"])
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["degraded_reasons"], ["shape_runtime_missing"])


class MultiViewEndpointTests(unittest.TestCase):
    def test_admits_full_coverage_without_calling_inference(self):
        views = [
            {"view_id": name, "evidence_class": "measured" if name == "front" else "synthetic", "sha256": "a" * 64}
            for name in ("front", "right", "back", "left", "top", "bottom")
        ]
        result = server.admit_multiview(server.MultiViewAdmissionRequest(views=views, profile="xreal"))
        self.assertTrue(result["ok"])
        self.assertTrue(result["admission"]["passed"])
        self.assertFalse(result["admission"]["synthetic_is_evidence"])

    def test_status_does_not_claim_single_view_mlx_is_multiview(self):
        result = server.multiview_status()
        self.assertFalse(result["available"])
        self.assertIn(result["reason_code"], {
            "multiview_weights_missing",
            "multiview_config_missing",
            "multiview_weights_incomplete",
            "multiview_physical_mac_certification_required",
        })


class DiskAdmissionTests(unittest.TestCase):
    def request(self, *, texture):
        return server.GenerateRequest(
            image_base64="A" * 32,
            texture=texture,
            category="product",
        )

    def test_geometry_only_admission_uses_smaller_conservative_reservation(self):
        usage = types.SimpleNamespace(free=server.MIN_FREE_DISK_BYTES_GEOMETRY)
        with mock.patch.object(server.shutil, "disk_usage", return_value=usage):
            report = server.ensure_generation_disk_space(self.request(texture=False))
        self.assertEqual(report["required_bytes"], server.MIN_FREE_DISK_BYTES_GEOMETRY)

    def test_textured_admission_rejects_insufficient_space_before_inference(self):
        usage = types.SimpleNamespace(free=server.MIN_FREE_DISK_BYTES_TEXTURE - 1)
        with mock.patch.object(server.shutil, "disk_usage", return_value=usage):
            with self.assertRaisesRegex(RuntimeError, "Espacio insuficiente"):
                server.ensure_generation_disk_space(self.request(texture=True))


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
