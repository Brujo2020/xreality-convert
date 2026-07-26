import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation_policy import normalize_generation_request


class ServerPolicyTest(unittest.TestCase):
    def test_lowpoly_is_never_used_for_animal_generation(self):
        request = SimpleNamespace(
            image_base64="x" * 32,
            category="animal",
            profile="lowpoly",
            steps=20,
            octree_resolution=128,
            target_faces=12000,
            texture=True,
            texture_size="1K",
        )
        normalized = normalize_generation_request(request)
        self.assertEqual(normalized.profile, "xreal")
        self.assertEqual(normalized.steps, 50)
        self.assertEqual(normalized.octree_resolution, 256)
        self.assertEqual(normalized.target_faces, 100000)
        self.assertEqual(normalized.texture_size, "1K")

    def test_lowpoly_remains_available_for_non_organic_assets(self):
        request = SimpleNamespace(
            image_base64="x" * 32,
            category="industrial",
            profile="lowpoly",
            steps=20,
            octree_resolution=128,
            target_faces=12000,
        )
        self.assertIs(normalize_generation_request(request), request)


if __name__ == "__main__":
    unittest.main()
