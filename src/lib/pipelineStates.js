import pipelineContract from '../../engine/pipeline_states.json';

export const PIPELINE_STATES = Object.fromEntries(
  pipelineContract.states.map((state) => [state.id, state])
);

export function getPipelineState(stateId) {
  return PIPELINE_STATES[stateId] || null;
}
