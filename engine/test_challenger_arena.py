import copy
import unittest

from challenger_arena import ArenaContractError, run_local_arena, seal_provider_report, validate_arena_spec, validate_provider_report


def hash_of(char):
    return "sha256:" + char * 64


def pins(model="a", code="b"):
    return {
        "model": {"repo": "local/provider", "revision": model * 40},
        "code": {"revision": code * 40},
    }


def spec():
    return {
        "schema_version": 1,
        "arena_id": "coffee-mug-corpus-v1",
        "corpus_sha256": hash_of("c"),
        "cases": [{"id": "mug-front", "required_lanes": ["geometry", "uv", "textures", "materials", "visual"]}],
        "providers": [
            {"id": "hunyuan-mlx", "role": "incumbent", "pins": pins("a", "b")},
            {"id": "trellis-apple", "role": "challenger", "pins": pins("d", "e")},
        ],
    }


def report(provider_id, provider_pins, quality=0.8, latency=10.0, memory=100, **overrides):
    lanes = {
        lane: {"status": "pass", "evidence_class": "measured", "score": quality}
        for lane in ("geometry", "uv", "textures", "materials", "visual")
    }
    lanes["visual"]["human_decision"] = "pass"
    value = {
        "schema_version": 1,
        "arena_id": "coffee-mug-corpus-v1",
        "provider_id": provider_id,
        "pins": provider_pins,
        "preflight": {"eligible": True, "promotion_ready": True, "reasons": []},
        "execution": {"offline": True, "network_allowed": False},
        "corpus_sha256": hash_of("c"),
        "cases": [{
            "case_id": "mug-front",
            "artifact": {"sha256": hash_of("f")},
            "lanes": lanes,
            "metrics": {"latency_seconds": latency, "peak_memory_bytes": memory},
        }],
    }
    value.update(overrides)
    return seal_provider_report(value)


class ChallengerArenaTests(unittest.TestCase):
    def test_challenger_can_lead_shadow_ranking_without_auto_promotion(self):
        incumbent = report("hunyuan-mlx", pins("a", "b"), quality=0.8, latency=8)
        challenger = report("trellis-apple", pins("d", "e"), quality=0.9, latency=20)
        result = run_local_arena(spec(), [incumbent, challenger])
        self.assertEqual(result["mode"], "local_sealed_shadow_only")
        self.assertEqual(result["ranking"][0]["provider"], "trellis-apple")
        self.assertEqual(result["shadow_outcome"]["status"], "challenger_outperforms_incumbent")
        self.assertFalse(result["promotion"]["allowed"])
        self.assertEqual(result["promotion"]["status"], "human_review_required")

    def test_missing_preflight_fails_closed_and_makes_comparison_inconclusive(self):
        incumbent = report("hunyuan-mlx", pins("a", "b"))
        challenger = report("trellis-apple", pins("d", "e"))
        challenger = copy.deepcopy(challenger)
        challenger.pop("preflight")
        challenger = seal_provider_report(challenger)
        result = run_local_arena(spec(), [incumbent, challenger])
        rejected = next(item for item in result["provider_results"] if item["provider"] == "trellis-apple")
        self.assertFalse(rejected["eligible"])
        self.assertIn("preflight_missing", rejected["reasons"])
        self.assertEqual(result["shadow_outcome"]["status"], "inconclusive")

    def test_missing_measured_lane_evidence_cannot_win(self):
        incumbent = report("hunyuan-mlx", pins("a", "b"))
        challenger = report("trellis-apple", pins("d", "e"), quality=1.0)
        challenger = copy.deepcopy(challenger)
        challenger["cases"][0]["lanes"]["visual"] = {"status": "not_measured", "evidence_class": "not_measured", "score": 1.0}
        challenger = seal_provider_report(challenger)
        validation = validate_provider_report(spec(), challenger)
        self.assertFalse(validation["eligible"])
        self.assertIn("lane_not_measured_pass:mug-front:visual", validation["reasons"])

    def test_report_pin_mismatch_fails_closed(self):
        bad = report("hunyuan-mlx", pins("d", "e"))
        validation = validate_provider_report(spec(), bad)
        self.assertFalse(validation["eligible"])
        self.assertIn("provider_pin_mismatch", validation["reasons"])

    def test_tampered_sealed_report_is_ineligible(self):
        bad = report("hunyuan-mlx", pins("a", "b"))
        bad["cases"][0]["metrics"]["latency_seconds"] = 0
        validation = validate_provider_report(spec(), bad)
        self.assertFalse(validation["eligible"])
        self.assertIn("invalid_or_missing_report_seal", validation["reasons"])

    def test_tie_breaks_by_provider_id_deterministically(self):
        local_spec = spec()
        local_spec["providers"] = [
            {"id": "hunyuan-mlx", "role": "incumbent", "pins": pins("a", "b")},
            {"id": "zeta", "role": "challenger", "pins": pins("d", "e")},
            {"id": "alpha", "role": "challenger", "pins": pins("f", "0")},
        ]
        reports = [
            report("hunyuan-mlx", pins("a", "b")),
            report("zeta", pins("d", "e")),
            report("alpha", pins("f", "0")),
        ]
        result = run_local_arena(local_spec, reports)
        self.assertEqual([item["provider"] for item in result["ranking"]], ["alpha", "hunyuan-mlx", "zeta"])

    def test_unrecognized_report_forces_inconclusive_shadow_outcome(self):
        result = run_local_arena(
            spec(),
            [report("hunyuan-mlx", pins("a", "b")), report("trellis-apple", pins("d", "e")), {"provider_id": "unknown"}],
        )
        self.assertEqual(result["unrecognized_provider_reports"], ["unknown"])
        self.assertEqual(result["shadow_outcome"]["status"], "inconclusive")

    def test_spec_requires_one_incumbent_and_sealed_corpus(self):
        invalid = spec()
        invalid["corpus_sha256"] = "unsealed"
        with self.assertRaisesRegex(ArenaContractError, "sealed_corpus_sha256_required"):
            validate_arena_spec(invalid)
        invalid = spec()
        invalid["providers"][1]["role"] = "incumbent"
        with self.assertRaisesRegex(ArenaContractError, "exactly_one_incumbent_required"):
            validate_arena_spec(invalid)


if __name__ == "__main__":
    unittest.main()
