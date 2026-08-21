import unittest

from multiview_contract import MultiViewContractError, admit_multiview_shape


def view(view_id, evidence="synthetic"):
    return {"view_id": view_id, "evidence_class": evidence, "sha256": "a" * 64}


class MultiViewContractTests(unittest.TestCase):
    def test_accepts_six_view_assist_but_marks_synthetic_not_evidence(self):
        views = [view("front", "measured")] + [view(item) for item in ("right", "back", "left", "top", "bottom")]
        report = admit_multiview_shape(views, profile="xreal")
        self.assertTrue(report["passed"])
        self.assertFalse(report["synthetic_is_evidence"])
        self.assertEqual(report["promotion"], "human_review_required")

    def test_rejects_master_without_six_real_views(self):
        views = [view("front", "measured")] + [view(item) for item in ("right", "back", "left", "top", "bottom")]
        with self.assertRaisesRegex(MultiViewContractError, "master_requires_six_real_views"):
            admit_multiview_shape(views, profile="maxquality")

    def test_rejects_duplicate_camera(self):
        with self.assertRaisesRegex(MultiViewContractError, "multiview_camera_invalid_or_duplicate"):
            admit_multiview_shape([view("front", "measured"), view("front")], profile="xreal")
