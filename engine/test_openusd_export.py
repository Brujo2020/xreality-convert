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


if __name__ == "__main__":
    unittest.main()
