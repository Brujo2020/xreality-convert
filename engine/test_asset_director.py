import unittest

from asset_director import (
    component_policy,
    material_profile_for_paint,
    normalize_category,
    normalize_material,
    optimize_delivery_settings,
    plan_asset,
)


class AssetDirectorTests(unittest.TestCase):
    def test_spanish_aliases_are_normalized(self):
        self.assertEqual(normalize_category("grúa"), "crane")
        self.assertEqual(normalize_category("bodega"), "warehouse")
        self.assertEqual(normalize_material("porcelana"), "porcelain")
        self.assertEqual(normalize_material("alformbra"), "carpet")

    def test_lowpoly_is_an_intent_and_stays_on_fast_paint(self):
        plan = plan_asset(
            category="vehicle",
            material_hint="painted_metal",
            profile="lowpoly",
            requested_paint_backend="agentic",
        )
        self.assertEqual(plan["category"], "vehicle")
        self.assertEqual(plan["archetype"], "hard_surface")
        self.assertEqual(plan["paint_backend"], "fast")
        self.assertEqual(plan["quality_tier"], "preview")

    def test_fast_request_is_respected_for_high_risk_single_view(self):
        plan = plan_asset(
            category="animal",
            material_hint="auto",
            profile="xreal",
            requested_paint_backend="fast",
        )
        self.assertEqual(plan["paint_backend"], "fast")
        self.assertFalse(plan["reference_lock"])
        self.assertEqual(plan["material"], "fur")

    def test_explicit_agentic_request_remains_agentic(self):
        plan = plan_asset(
            category="vehicle", profile="maxquality", requested_paint_backend="agentic"
        )
        self.assertEqual(plan["paint_backend"], "agentic")
        self.assertTrue(plan["reference_lock"])

    def test_vehicle_gets_dielectric_clearcoat_contract(self):
        plan = plan_asset(category="vehicle", profile="pcvr")
        contract = plan["material_contract"]
        self.assertEqual(plan["material"], "painted_metal")
        self.assertIn("KHR_materials_clearcoat", contract["extensions"])
        self.assertEqual(contract["metallic_range"][0], 0.0)
        self.assertEqual(contract["recommended_material_regions"], 3)

    def test_glass_requires_transmission_volume_and_ior(self):
        contract = plan_asset(
            category="product", material_hint="glass", profile="xreal"
        )["material_contract"]
        self.assertEqual(
            set(contract["extensions"]),
            {
                "KHR_materials_transmission",
                "KHR_materials_volume",
                "KHR_materials_ior",
            },
        )

    def test_master_microdetail_is_fail_closed(self):
        plan = plan_asset(
            category="person", material_hint="skin", profile="maxquality"
        )
        self.assertTrue(plan["enforce_recommended_maps"])
        self.assertIn("normal", plan["material_contract"]["recommended_maps"])

    def test_watertightness_is_strict_only_for_closed_master_assets(self):
        xr_product = plan_asset(category="product", profile="xreal")
        master_product = plan_asset(category="product", profile="maxquality")
        master_truck = plan_asset(category="truck", profile="maxquality")

        self.assertTrue(xr_product["geometry_contract"]["prefer_watertight"])
        self.assertFalse(xr_product["geometry_contract"]["require_watertight"])
        self.assertEqual(
            xr_product["geometry_contract"]["watertight_policy"], "preferred_xr"
        )
        self.assertTrue(master_product["geometry_contract"]["require_watertight"])
        self.assertFalse(master_truck["geometry_contract"]["prefer_watertight"])
        self.assertFalse(master_truck["geometry_contract"]["require_watertight"])

    def test_complex_assemblies_are_preserved(self):
        for category in (
            "industrial", "construction", "warehouse", "crane", "vehicle",
            "cargo_vehicle", "truck", "electrical", "vegetation", "building", "tool",
            "forklift", "excavator", "motorcycle", "bus", "drone", "boat", "furniture", "solar",
        ):
            with self.subTest(category=category):
                self.assertTrue(component_policy(category)["preserve_assembly"])

    def test_buffalo_strategy_is_an_explicit_non_official_semantic_contract(self):
        plan = plan_asset(category="crane", profile="xreal")
        semantic = plan["semantic_contract"]

        self.assertEqual(plan["version"], 2)
        self.assertFalse(semantic["provenance"]["official_buffalo_code_or_weights"])
        self.assertIn("hook", semantic["critical_part_names"])
        self.assertEqual(semantic["semantic_evidence_status"], "not_measured")

    def test_new_spanish_template_aliases_have_specific_contracts(self):
        expected = {
            "vehículo de carga": "cargo_vehicle",
            "camión": "truck",
            "instalación eléctrica": "electrical",
            "vegetación": "vegetation",
            "edificio": "building",
            "herramienta": "tool",
            "montacargas": "forklift",
            "excavadora": "excavator",
            "motocicleta": "motorcycle",
            "autobús": "bus",
            "dron": "drone",
            "embarcación": "boat",
            "mobiliario": "furniture",
            "energía solar": "solar",
        }
        for label, category in expected.items():
            with self.subTest(label=label):
                self.assertEqual(normalize_category(label), category)

    def test_lowpoly_is_textured_and_capped_without_a_second_backend(self):
        settings = optimize_delivery_settings(
            profile="lowpoly",
            steps=50,
            octree_resolution=256,
            target_faces=200000,
            texture_resolution=2048,
            paint_backend="agentic",
            unified_memory_gb=64,
        )
        self.assertEqual(settings["steps"], 24)
        self.assertEqual(settings["octree_resolution"], 128)
        self.assertEqual(settings["target_faces"], 15000)
        self.assertEqual(settings["texture_resolution"], 1024)
        self.assertEqual(settings["paint_backend"], "fast")
        self.assertTrue(settings["preserve_master"])

    def test_vr_ready_has_a_portable_delivery_budget(self):
        settings = optimize_delivery_settings(
            profile="vrready", steps=40, octree_resolution=256,
            target_faces=100000, texture_resolution=2048,
        )
        self.assertEqual(settings["steps"], 32)
        self.assertEqual(settings["octree_resolution"], 192)
        self.assertEqual(settings["target_faces"], 45000)
        self.assertEqual(settings["texture_resolution"], 1024)

    def test_smart_profile_scales_by_unified_memory(self):
        lean = optimize_delivery_settings(
            profile="smart", steps=50, octree_resolution=256,
            target_faces=200000, texture_resolution=2048, unified_memory_gb=16,
        )
        capable = optimize_delivery_settings(
            profile="smart", steps=50, octree_resolution=256,
            target_faces=200000, texture_resolution=2048, unified_memory_gb=64,
        )
        self.assertEqual(lean["strategy"], "smart_memory_guard")
        self.assertEqual(lean["target_faces"], 35000)
        self.assertEqual(capable["strategy"], "smart_throughput")
        self.assertEqual(capable["target_faces"], 80000)

    def test_fast_backend_uses_its_own_memory_budget(self):
        plan = plan_asset(
            category="animal",
            profile="xreal",
            requested_paint_backend="fast",
            unified_memory_gb=16,
        )
        self.assertFalse(plan["blocked"])
        self.assertEqual(plan["paint_backend"], "fast")

    def test_single_view_crane_cannot_be_called_master(self):
        plan = plan_asset(
            category="crane",
            material_hint="painted_metal",
            profile="maxquality",
            real_reference_views=1,
        )
        self.assertTrue(plan["blocked"])
        self.assertIn("master_requires_3_real_reference_views", plan["blockers"])

    def test_material_profiles_bridge_to_current_paint_engine(self):
        self.assertEqual(material_profile_for_paint("porcelain"), "porcelain")
        self.assertEqual(material_profile_for_paint("painted_metal"), "matte_paint")


if __name__ == "__main__":
    unittest.main()
