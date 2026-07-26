import unittest

import numpy as np

from material_policy import apply_material_prior, resolve_material_profile


class MaterialPolicyTests(unittest.TestCase):
    def test_category_resolves_safe_organic_defaults(self):
        self.assertEqual(resolve_material_profile("auto", "animal"), "animal")
        self.assertEqual(resolve_material_profile("auto", "person"), "person")
        self.assertEqual(resolve_material_profile("auto", "industrial"), "auto")

    def test_animal_is_dielectric_and_rough(self):
        source = np.ones((2, 2, 3), dtype=np.float32)
        result, report = apply_material_prior(source, "animal")
        self.assertTrue(report["material_prior_applied"])
        self.assertLessEqual(float(result[..., 0].max()), 0.02)
        self.assertGreaterEqual(float(result[..., 1].min()), 0.62)
        np.testing.assert_array_equal(source, np.ones((2, 2, 3), dtype=np.float32))

    def test_rust_and_metal_have_distinct_physical_ranges(self):
        source = np.full((1, 1, 3), 0.5, dtype=np.float32)
        rust, _ = apply_material_prior(source, "rust")
        metal, _ = apply_material_prior(source, "metal")
        self.assertLess(float(rust[0, 0, 0]), float(metal[0, 0, 0]))
        self.assertGreater(float(rust[0, 0, 1]), float(metal[0, 0, 1]))


if __name__ == "__main__":
    unittest.main()
