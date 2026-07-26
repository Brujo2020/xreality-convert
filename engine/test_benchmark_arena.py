import json
import tempfile
import unittest
from pathlib import Path

from benchmark_arena import blind_candidate_order, canonical_json, seal_corpus


class BenchmarkArenaTests(unittest.TestCase):
    def test_seals_only_manifested_assets_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "front.png").write_bytes(b"front")
            manifest = {
                "schemaVersion": 1,
                "items": [{"id": "animal-01", "assets": ["front.png"]}],
            }
            (root / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")

            first = seal_corpus(root)
            second = seal_corpus(root)

            self.assertEqual(first, second)
            self.assertEqual(first["itemCount"], 1)
            self.assertEqual(
                [entry["path"] for entry in first["files"]],
                ["corpus.json", "front.png"],
            )
            self.assertEqual(len(first["corpusId"]), 64)

    def test_asset_change_creates_new_corpus_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / "front.png"
            asset.write_bytes(b"version-1")
            (root / "corpus.json").write_text(json.dumps({
                "schemaVersion": 1,
                "items": [{"id": "object-01", "assets": ["front.png"]}],
            }), encoding="utf-8")
            original = seal_corpus(root)["corpusId"]

            asset.write_bytes(b"version-2")

            self.assertNotEqual(original, seal_corpus(root)["corpusId"])

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "corpus.json").write_text(json.dumps({
                "schemaVersion": 1,
                "items": [{"id": "unsafe", "assets": ["../secret.png"]}],
            }), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unsafe_asset_path"):
                seal_corpus(root)

    def test_blind_order_is_stable_and_hides_provider_names_in_labels(self):
        manifests = ["rodin-manifest", "xreality-manifest", "tripo-manifest"]

        first = blind_candidate_order("spec-1", "animal-01", 2026, manifests)
        second = blind_candidate_order("spec-1", "animal-01", 2026, manifests)

        self.assertEqual(first, second)
        self.assertEqual(
            [entry["label"] for entry in first],
            ["candidate-01", "candidate-02", "candidate-03"],
        )
        self.assertEqual({entry["manifestId"] for entry in first}, set(manifests))

    def test_canonical_json_rejects_float_identity_values(self):
        with self.assertRaisesRegex(ValueError, "floating_point_not_allowed"):
            canonical_json({"threshold": 0.5})


if __name__ == "__main__":
    unittest.main()
