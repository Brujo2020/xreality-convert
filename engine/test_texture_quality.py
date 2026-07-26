import unittest

import numpy as np
from PIL import Image, ImageDraw

from texture_quality import align_reference_to_geometry


class TextureQualityTest(unittest.TestCase):
    def test_aligns_subject_to_geometry_silhouette(self):
        reference = Image.new("RGB", (100, 100), "white")
        ImageDraw.Draw(reference).rectangle((30, 20, 69, 79), fill=(180, 70, 30))
        geometry = Image.new("RGB", (200, 200), "black")
        ImageDraw.Draw(geometry).rectangle((60, 40, 139, 159), fill=(128, 128, 255))

        aligned, report = align_reference_to_geometry(
            reference,
            geometry,
            (200, 200),
        )

        self.assertIsNotNone(aligned)
        self.assertTrue(report["passed"])
        self.assertGreater(report["silhouette_iou"], 0.95)
        self.assertEqual(aligned.getpixel((100, 100)), (180, 70, 30))

    def test_rejects_image_without_detectable_subject(self):
        reference = Image.new("RGB", (100, 100), "white")
        geometry = Image.new("RGB", (100, 100), "black")
        ImageDraw.Draw(geometry).ellipse((20, 20, 80, 80), fill="white")

        aligned, report = align_reference_to_geometry(
            reference,
            geometry,
            (100, 100),
        )

        self.assertIsNone(aligned)
        self.assertFalse(report["passed"])
        self.assertEqual(report["reason"], "foreground_not_detected")

    def test_rejects_extreme_silhouette_aspect_mismatch(self):
        reference_array = np.full((100, 100, 3), 255, dtype=np.uint8)
        reference_array[45:55, 10:90] = (80, 40, 20)
        reference = Image.fromarray(reference_array)
        geometry = Image.new("RGB", (100, 100), "black")
        ImageDraw.Draw(geometry).rectangle((45, 10, 55, 90), fill="white")

        aligned, report = align_reference_to_geometry(
            reference,
            geometry,
            (100, 100),
        )

        self.assertIsNone(aligned)
        self.assertFalse(report["passed"])
        self.assertEqual(report["reason"], "silhouette_aspect_mismatch")

    def test_rejects_weak_silhouette_overlap(self):
        reference = Image.new("RGB", (100, 100), "white")
        ImageDraw.Draw(reference).rectangle((20, 10, 79, 89), fill=(180, 70, 30))
        geometry = Image.new("RGB", (100, 100), "black")
        geometry_draw = ImageDraw.Draw(geometry)
        geometry_draw.rectangle((45, 10, 54, 89), fill="white")
        geometry_draw.rectangle((20, 45, 79, 54), fill="white")

        aligned, report = align_reference_to_geometry(reference, geometry, (100, 100))

        self.assertIsNone(aligned)
        self.assertFalse(report["passed"])
        self.assertEqual(report["reason"], "silhouette_overlap_too_low")

if __name__ == "__main__":
    unittest.main()
