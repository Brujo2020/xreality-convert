import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from buffalo_runtime import canonical_json
from canonical_render_evidence import (
    CanonicalRenderEvidenceError,
    bind_canonical_render_evidence,
    verify_canonical_render_evidence,
)


def sha256(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_glb(path, *, alpha=False):
    material = {"alphaMode": "BLEND"} if alpha else {}
    document = {"asset": {"version": "2.0"}, "nodes": [{}], "materials": [material]}
    encoded = json.dumps(document, sort_keys=True).encode("utf-8")
    encoded += b" " * ((-len(encoded)) % 4)
    path.write_bytes(
        struct.pack("<III", 0x46546C67, 2, 20 + len(encoded))
        + struct.pack("<II", len(encoded), 0x4E4F534A)
        + encoded
    )


def write_graph(path):
    payload = {
        "schema_version": 1,
        "category": "product",
        "root_id": "category:1234567890abcdef",
        "nodes": [
            {"id": "category:1234567890abcdef", "kind": "category", "canonical_name": "product"},
            {"id": "part:1234567890abcdef", "kind": "part", "canonical_name": "body"},
        ],
        "edges": [{"source": "category:1234567890abcdef", "target": "part:1234567890abcdef", "type": "contains_part"}],
    }
    graph = {**payload, "graph_id": "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()}
    path.write_text(json.dumps(graph), encoding="utf-8")
    return graph


def write_external_report(job, *, alpha=False):
    glb = job / "asset.glb"
    graph_path = job / "semantic-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    modes = [
        "unlit", "neutral-front", "neutral-quarter-left", "neutral-quarter-right",
        "grazing", "wireframe", "semantic-part",
    ]
    if alpha:
        modes.append("alpha-transmission-checker")
    runner = {"producer": "local-blender-canonical", "execution_id": "run-0001"}
    renders = []
    render_root = job / "canonical"
    render_root.mkdir(exist_ok=True)
    for mode in modes:
        image = render_root / f"{mode}.png"
        metadata = render_root / f"{mode}.json"
        image.write_bytes(("external measured image " + mode).encode("utf-8"))
        metadata.write_text(json.dumps({
            "schema_version": 1,
            "kind": "xreality.blender_canonical_render_meta",
            "mode": mode,
            "runner": runner,
            "artifact": {"sha256": sha256(glb)},
            "semantic_graph": {"sha256": sha256(graph_path), "graph_id": graph["graph_id"]},
            "render": {"path": image.relative_to(job).as_posix(), "sha256": sha256(image)},
        }), encoding="utf-8")
        renders.append({
            "mode": mode,
            "path": image.relative_to(job).as_posix(),
            "sha256": sha256(image),
            "metadata_path": metadata.relative_to(job).as_posix(),
            "metadata_sha256": sha256(metadata),
        })
    report = {
        "schema_version": 1,
        "kind": "xreality.blender_canonical_render_report",
        "status": "pass",
        "measurement": {"kind": "external_blender_canonical_render", "executed": True, "exit_code": 0},
        "runner": runner,
        "artifact": {"path": "asset.glb", "sha256": sha256(glb)},
        "semantic_graph": {"path": "semantic-graph.json", "sha256": sha256(graph_path), "graph_id": graph["graph_id"]},
        "renders": renders,
    }
    path = render_root / "blender-canonical-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path, renders


class CanonicalRenderEvidenceTests(unittest.TestCase):
    def make_job(self, directory, *, alpha=False):
        job = Path(directory) / "job"
        job.mkdir()
        write_glb(job / "asset.glb", alpha=alpha)
        write_graph(job / "semantic-graph.json")
        return job

    def test_binds_full_external_matrix_and_revalidates_sealed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            job = self.make_job(directory)
            report, _ = write_external_report(job)
            bound = bind_canonical_render_evidence(
                job_dir=job, glb_path="asset.glb", semantic_graph_path="semantic-graph.json",
                render_report_path=report.relative_to(job).as_posix(),
            )
            self.assertEqual(bound["status"], "measured_pass")
            self.assertFalse(bound["requirements"]["alpha_transmission_checker_required"])
            self.assertEqual(len(bound["renders"]), 7)
            evidence_path = Path(bound["path"])
            self.assertFalse(evidence_path.stat().st_mode & 0o200)
            verified = verify_canonical_render_evidence(
                job_dir=job, record_path=evidence_path.relative_to(job.resolve()).as_posix(),
            )
            self.assertEqual(verified["record_id"], bound["record_id"])

    def test_requires_alpha_checker_only_for_alpha_or_transmissive_materials(self):
        with tempfile.TemporaryDirectory() as directory:
            job = self.make_job(directory, alpha=True)
            report, renders = write_external_report(job, alpha=True)
            bound = bind_canonical_render_evidence(
                job_dir=job, glb_path="asset.glb", semantic_graph_path="semantic-graph.json",
                render_report_path=report.relative_to(job).as_posix(),
            )
            self.assertTrue(bound["requirements"]["alpha_transmission_checker_required"])
            self.assertIn("alpha-transmission-checker", [entry["mode"] for entry in bound["renders"]])
            report.chmod(0o600)  # Simulate a malicious/local administrator mutation.
            payload = json.loads(report.read_text(encoding="utf-8"))
            payload["renders"] = [item for item in payload["renders"] if item["mode"] != "alpha-transmission-checker"]
            report.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(CanonicalRenderEvidenceError, "canonical_render_matrix_incomplete"):
                bind_canonical_render_evidence(
                    job_dir=job, glb_path="asset.glb", semantic_graph_path="semantic-graph.json",
                    render_report_path=report.relative_to(job).as_posix(),
                )

    def test_never_synthesizes_missing_or_incomplete_render_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            job = self.make_job(directory)
            with self.assertRaisesRegex(CanonicalRenderEvidenceError, "canonical_render_report_missing"):
                bind_canonical_render_evidence(
                    job_dir=job, glb_path="asset.glb", semantic_graph_path="semantic-graph.json",
                    render_report_path="canonical/missing.json",
                )
            self.assertFalse((job / "canonical-render-evidence").exists())
            report, _ = write_external_report(job)
            payload = json.loads(report.read_text(encoding="utf-8"))
            payload["renders"] = payload["renders"][:-1]
            report.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(CanonicalRenderEvidenceError, "canonical_render_matrix_incomplete"):
                bind_canonical_render_evidence(
                    job_dir=job, glb_path="asset.glb", semantic_graph_path="semantic-graph.json",
                    render_report_path=report.relative_to(job).as_posix(),
                )

    def test_verification_detects_post_bind_frame_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            job = self.make_job(directory)
            report, renders = write_external_report(job)
            bound = bind_canonical_render_evidence(
                job_dir=job, glb_path="asset.glb", semantic_graph_path="semantic-graph.json",
                render_report_path=report.relative_to(job).as_posix(),
            )
            frame = job / renders[0]["path"]
            frame.chmod(0o600)  # The verifier must still detect tampering.
            frame.write_bytes(b"tampered")
            with self.assertRaisesRegex(CanonicalRenderEvidenceError, "canonical_render_hash_mismatch"):
                verify_canonical_render_evidence(
                    job_dir=job, record_path=Path(bound["path"]).relative_to(job.resolve()).as_posix(),
                )


if __name__ == "__main__":
    unittest.main()
