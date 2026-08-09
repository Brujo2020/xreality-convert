import hashlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from benchmark_arena import audit_glb, preflight, rank_reports, review_visual_evidence, seal_corpus, validate_spec


def png_512():
    output = io.BytesIO()
    Image.new("RGB", (512, 512), (180, 90, 40)).save(output, format="PNG")
    return output.getvalue()


def write_glb(path, pbr=True, uv=True, degenerate=False, texture=None):
    texture = png_512() if texture is None else texture
    positions = [(0, 0, 0), (0, 0, 0), (0, 0, 0)] if degenerate else [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    blobs = [struct.pack("<9f", *(value for point in positions for value in point))]
    if uv:
        blobs.append(struct.pack("<6f", 0, 0, 1, 0, 0, 1))
    blobs.append(struct.pack("<3H", 0, 1, 2))
    if pbr:
        blobs.extend([texture, texture])
    binary = b""
    views = []
    for blob in blobs:
        binary += b"\x00" * ((4 - len(binary) % 4) % 4)
        views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(blob)})
        binary += blob
    accessors = [
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": 3,
            "type": "VEC3",
            "min": [min(point[i] for point in positions) for i in range(3)],
            "max": [max(point[i] for point in positions) for i in range(3)],
        }
    ]
    attributes = {"POSITION": 0}
    index_view = 1
    if uv:
        accessors.append({"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC2", "min": [0, 0], "max": [1, 1]})
        attributes["TEXCOORD_0"] = 1
        index_view = 2
    accessors.append({"bufferView": index_view, "componentType": 5123, "count": 3, "type": "SCALAR", "min": [0], "max": [2]})
    primitive = {"attributes": attributes, "indices": len(accessors) - 1}
    document = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
        "meshes": [{"primitives": [primitive]}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    if pbr:
        primitive["material"] = 0
        image_start = index_view + 1
        document.update(
            images=[{"bufferView": image_start, "mimeType": "image/png"}, {"bufferView": image_start + 1, "mimeType": "image/png"}],
            textures=[{"source": 0}, {"source": 1}],
            materials=[{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicRoughnessTexture": {"index": 1}}}],
        )
    json_chunk = json.dumps(document, separators=(",", ":")).encode()
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    binary += b"\x00" * ((4 - len(binary) % 4) % 4)
    chunks = struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk
    chunks += struct.pack("<II", len(binary), 0x004E4942) + binary
    Path(path).write_bytes(b"glTF" + struct.pack("<II", 2, 12 + len(chunks)) + chunks)


class SpecTests(unittest.TestCase):
    def provider(self):
        return {
            "id": "p",
            "state": "candidate",
            "capabilities": {"image_to_mesh": True},
            "model": {
                "repo": "a/b",
                "revision": "a" * 40,
                "artifacts": [{"path": "w.bin", "size": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}],
            },
        }

    def test_accepts_pinned_provider(self):
        self.assertEqual(validate_spec({"schema_version": 1, "providers": [self.provider()]})["schema_version"], 1)

    def test_rejects_floating_revision(self):
        provider = self.provider()
        provider["model"]["revision"] = "main"
        with self.assertRaisesRegex(ValueError, "unpinned_model"):
            validate_spec({"schema_version": 1, "providers": [provider]})

    def test_rejects_artifact_traversal(self):
        provider = self.provider()
        provider["model"]["artifacts"][0]["path"] = "../secret"
        with self.assertRaisesRegex(ValueError, "unsafe_relative_path"):
            validate_spec({"schema_version": 1, "providers": [provider]})

    def test_preflight_detects_complete_and_missing_snapshots(self):
        provider = self.provider()
        spec = {"schema_version": 1, "providers": [provider]}
        with tempfile.TemporaryDirectory() as cache, tempfile.TemporaryDirectory() as root:
            snapshot = Path(cache) / "models--a--b" / "snapshots" / ("a" * 40)
            snapshot.mkdir(parents=True)
            (snapshot / "w.bin").write_bytes(b"abc")
            self.assertTrue(preflight(spec, cache, root, deep=True)["providers"][0]["promotion_ready"])
            (snapshot / "w.bin").unlink()
            self.assertIn("model_artifacts_incomplete", preflight(spec, cache, root)["providers"][0]["reasons"])

    def test_orchestrator_is_never_eligible_as_3d_provider(self):
        provider = self.provider()
        provider.update(state="orchestrator", role="judge")
        with tempfile.TemporaryDirectory() as cache, tempfile.TemporaryDirectory() as root:
            report = preflight({"schema_version": 1, "providers": [provider]}, cache, root)["providers"][0]
            self.assertFalse(report["eligible"])


class CorpusTests(unittest.TestCase):
    def test_seal_is_deterministic(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "a.png").write_bytes(b"image")
            corpus = {"cases": [{"id": "a", "lanes": ["shape"], "assets": {"image": "a.png"}}]}
            self.assertEqual(seal_corpus(corpus, root), seal_corpus(corpus, root))

    def test_seal_rejects_escape(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "unsafe_relative_path"):
                seal_corpus({"cases": [{"id": "a", "assets": {"image": "../a"}}]}, root)


class ArtifactTests(unittest.TestCase):
    def test_shape_glb_passes_without_claiming_pbr(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "shape.glb")
            write_glb(path, pbr=False, uv=False)
            report = audit_glb(path)
            self.assertTrue(report["passed"])
            self.assertEqual(report["visual_quality"], "not_measured")

    def test_pbr_glb_passes_all_structural_lanes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "pbr.glb")
            write_glb(path)
            report = audit_glb(path, require_pbr=True)
            self.assertTrue(report["passed"])
            self.assertEqual(report["pbr_score"], 40)
            self.assertFalse(report["promotion_passed"])

    def test_pbr_rejects_missing_uv(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "no-uv.glb")
            write_glb(path, uv=False)
            self.assertFalse(audit_glb(path, require_pbr=True)["passed"])

    def test_geometry_rejects_degenerate_triangle(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "flat.glb")
            write_glb(path, pbr=False, degenerate=True)
            self.assertFalse(audit_glb(path)["gates"]["geometry"])

    def test_texture_gate_rejects_invalid_png_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "fake.glb")
            write_glb(path, texture=b"not-png")
            self.assertFalse(audit_glb(path, require_pbr=True)["gates"]["textures"])

    def test_invalid_glb_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "invalid.glb")
            path.write_bytes(b"bad")
            self.assertFalse(audit_glb(path)["passed"])

    def test_visual_review_rejects_permissive_upstream_pass(self):
        evidence = {
            "gate": {
                "passed": True,
                "front": {"metrics": {"silhouetteIoU": 0.7823, "spatialColorCorrelation": 0.7718}},
                "quarters": {"metrics": {
                    "quarter-left": {"paletteSimilarity": 0.9331, "colorRetention": 0.9732},
                    "quarter-right": {"paletteSimilarity": 0.9163, "colorRetention": 1.0},
                }},
            }
        }
        report = review_visual_evidence(evidence, "reject")
        self.assertFalse(report["automatic_passed"])
        self.assertEqual(report["visual_quality"], "reject")
        self.assertIn("silhouette", report["reasons"])
        self.assertIn("spatial_color", report["reasons"])

    def test_visual_review_requires_human_acceptance(self):
        evidence = {
            "gate": {
                "passed": True,
                "front": {"metrics": {"silhouetteIoU": 0.9, "spatialColorCorrelation": 0.9}},
                "quarters": {"metrics": {
                    "quarter-left": {"paletteSimilarity": 0.9, "colorRetention": 0.9},
                    "quarter-right": {"paletteSimilarity": 0.9, "colorRetention": 0.9},
                }},
            }
        }
        self.assertFalse(review_visual_evidence(evidence)["passed"])
        self.assertTrue(review_visual_evidence(evidence, "pass")["passed"])

    def test_rank_ignores_judges_and_unreviewed_artifacts(self):
        reports = [
            {"provider": "judge", "role": "judge", "passed": True, "promotion_passed": True, "structural_score": 100},
            {"provider": "structural-only", "passed": True, "promotion_passed": False, "structural_score": 90},
            {"provider": "winner", "passed": True, "promotion_passed": True, "structural_score": 80},
        ]
        self.assertEqual(rank_reports(reports)["winner"], "winner")


if __name__ == "__main__":
    unittest.main()
