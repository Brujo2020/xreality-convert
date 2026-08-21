import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
import trimesh

from openusd_export import convert_glb_to_usdz, write_usda
from pbr_glb import _read_glb, _write_glb


def textured_glb(path):
    mesh = trimesh.creation.box()
    uv = np.zeros((len(mesh.vertices), 2), dtype=float)
    uv[:, 0] = np.linspace(0.0, 1.0, len(mesh.vertices))
    uv[:, 1] = np.linspace(1.0, 0.0, len(mesh.vertices))
    material = trimesh.visual.material.PBRMaterial(
        baseColorFactor=(255, 255, 255, 255),
        metallicFactor=0.75,
        roughnessFactor=0.35,
        baseColorTexture=Image.new("RGBA", (4, 4), (220, 40, 20, 255)),
        metallicRoughnessTexture=Image.new("RGB", (4, 4), (0, 90, 190)),
    )
    mesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv, material=material)
    mesh.export(path)
    document, binary = _read_glb(path)
    document.setdefault("asset", {}).setdefault("extras", {})["xrealityBuffaloMLX"] = {
        "strategy": "xreality-buffalo-mlx-v1",
        "preservation_passed": True,
    }
    _write_glb(path, document, binary)


class OpenUsdExportTests(unittest.TestCase):
    def test_usda_contains_mesh_uv_pbr_textures_and_manifest(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            glb = root / "asset.glb"
            textured_glb(glb)
            metrics = write_usda(glb, root / "asset.usda", root / "textures")
            stage = (root / "asset.usda").read_text(encoding="utf-8")

            self.assertIn('defaultPrim = "XrealityAsset"', stage)
            self.assertIn('uniform token info:id = "UsdPreviewSurface"', stage)
            self.assertIn("primvars:st", stage)
            self.assertIn("MetallicRoughness.outputs:b", stage)
            self.assertIn("MetallicRoughness.outputs:g", stage)
            self.assertIn("xreality:buffaloManifest", stage)
            self.assertEqual(metrics["meshes"], 1)
            self.assertEqual(metrics["textures"], 2)
            self.assertTrue(metrics["semantic_manifest_preserved"])

    @unittest.skipUnless(
        Path("/usr/bin/usdzip").exists() and Path("/usr/bin/usdchecker").exists(),
        "Apple OpenUSD tools are unavailable",
    )
    def test_usdz_passes_strict_realitykit_validation(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            glb = root / "asset.glb"
            textured_glb(glb)
            report = convert_glb_to_usdz(glb, root / "exports")

            self.assertTrue(report["ok"])
            self.assertTrue(report["arkit_compatible"])
            self.assertEqual(len(report["sha256"]), 64)
            self.assertTrue(Path(report["usdz_path"]).is_file())
            self.assertGreater(Path(report["usdz_path"]).stat().st_size, 0)

    def test_usda_with_parts(self):
        from openusd_export import write_usda_with_parts
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            glb1 = root / "part1.glb"
            glb2 = root / "part2.glb"
            textured_glb(glb1)
            textured_glb(glb2)
            
            parts_manifest = [
                {"label": "body", "glb_path": str(glb1)},
                {"label": "head", "glb_path": str(glb2)}
            ]
            
            usda_path = root / "asset_parts.usda"
            metrics = write_usda_with_parts(glb1, parts_manifest, usda_path, root / "textures")
            
            self.assertEqual(metrics["parts_count"], 2)
            stage = usda_path.read_text(encoding="utf-8")
            self.assertIn('def Xform "Geometry"', stage)
            self.assertIn('def Xform "Part_body"', stage)
            self.assertIn('def Xform "Part_head"', stage)
            self.assertIn('xreality:materialx_ready = "true"', stage)

    def test_usda_with_lods(self):
        from openusd_export import convert_glb_to_usd_production
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            glb1 = root / "lod0.glb"
            glb2 = root / "lod1.glb"
            textured_glb(glb1)
            textured_glb(glb2)
            
            # Use convert_glb_to_usd_production without usdzip by mocking or catching
            # For this test, we can just check write_usda_with_lods
            from openusd_export import write_usda_with_lods
            usda_path = root / "asset_lods.usda"
            metrics = write_usda_with_lods(glb1, [glb1, glb2], usda_path, root / "textures")
            
            self.assertEqual(len(metrics["lod_variants"]), 2)
            stage = usda_path.read_text(encoding="utf-8")
            self.assertIn('variantSet "LOD"', stage)
            self.assertIn('"LOD0" {', stage)
            self.assertIn('"LOD1" {', stage)
            self.assertIn('xreality:materialx_ready = "true"', stage)

    @unittest.skipUnless(
        Path("/usr/bin/usdzip").exists(),
        "usdzip is unavailable",
    )
    def test_production_export_pipeline(self):
        from openusd_export import convert_glb_to_usd_production
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            glb = root / "asset.glb"
            textured_glb(glb)
            
            parts_manifest = [{"label": "base", "glb_path": str(glb)}]
            report = convert_glb_to_usd_production(glb, root / "exports", parts=parts_manifest)
            
            self.assertTrue(report["ok"])
            self.assertTrue(report["materialx_compatible"])
            self.assertEqual(report["parts_count"], 1)
            self.assertIn("PartHierarchy", report["realitykit_features"])
            self.assertTrue(Path(report["usdz_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
