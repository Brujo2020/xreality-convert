import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_states import PIPELINE_STATES, pipeline_state


class PipelineStatesTest(unittest.TestCase):
    def test_required_states_have_labels_and_progress(self):
        for state_id in (
            "queued",
            "preparing",
            "input_saved",
            "isolating",
            "reference_ready",
            "loading",
            "model_ready",
            "reconstructing",
            "mesh_ready",
            "optimizing",
            "mesh_cleaned",
            "quality_checked",
            "mesh_simplified",
            "delivery_ready",
            "packaging",
            "glb_exported",
            "lods_exported",
            "report_saved",
            "done",
            "error",
        ):
            state = pipeline_state(state_id)
            self.assertEqual(state["id"], state_id)
            self.assertIsInstance(state["label"], str)
            self.assertGreaterEqual(state["progress"], 0)
            self.assertLessEqual(state["progress"], 100)

    def test_state_ids_are_unique(self):
        self.assertEqual(len(PIPELINE_STATES), len(set(PIPELINE_STATES)))

    def test_progress_is_monotonic_for_running_states(self):
        running_states = [
            state for state in PIPELINE_STATES.values()
            if state["id"] not in {"cancelled", "error"}
        ]
        progresses = [state["progress"] for state in running_states]
        self.assertEqual(progresses, sorted(progresses))


if __name__ == "__main__":
    unittest.main()
