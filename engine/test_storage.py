import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import storage


class StorageTest(unittest.TestCase):
    def test_has_free_space_checks_available_bytes(self):
        with mock.patch("storage.free_bytes", return_value=1024):
            self.assertTrue(storage.has_free_space("/tmp", 1024))
            self.assertFalse(storage.has_free_space("/tmp", 1025))

    def test_format_gb_is_human_readable(self):
        self.assertEqual(storage.format_gb(1536 * 1024 * 1024), 1.5)

    def test_cleanup_old_temporaries_preserves_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_png = root / "old.png"
            old_prepared = root / "old-prepared.png"
            old_glb = root / "old.glb"
            recent_png = root / "recent.png"
            for path in (old_png, old_prepared, old_glb, recent_png):
                path.write_text("x")
            os.utime(old_png, (100, 100))
            os.utime(old_prepared, (100, 100))
            os.utime(old_glb, (100, 100))
            os.utime(recent_png, (900, 900))

            removed = storage.cleanup_old_temporaries(root, older_than_seconds=300, now=1000)

            self.assertEqual(set(removed), {"old.png", "old-prepared.png"})
            self.assertFalse(old_png.exists())
            self.assertFalse(old_prepared.exists())
            self.assertTrue(old_glb.exists())
            self.assertTrue(recent_png.exists())


if __name__ == "__main__":
    unittest.main()
