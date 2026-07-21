import json
from pathlib import Path


STATES_PATH = Path(__file__).resolve().with_name("pipeline_states.json")
PIPELINE_STATES = {item["id"]: item for item in json.loads(STATES_PATH.read_text())["states"]}


def pipeline_state(state_id):
    return PIPELINE_STATES[state_id]
