#!/bin/zsh
set -euo pipefail

ENGINE_DIR="${0:A:h}"
PYTHON_RUNTIME="$(/bin/zsh "$ENGINE_DIR/setup.sh" --find-python)"
LOCAL_SITE_PACKAGES="$ENGINE_DIR/venv/lib/python3.11/site-packages"

if [[ -d "$LOCAL_SITE_PACKAGES" ]]; then
  export PYTHONPATH="$LOCAL_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
fi

cd "$ENGINE_DIR"
exec "$PYTHON_RUNTIME" -m unittest \
  test_server_pipeline \
  test_pbr_glb \
  test_material_policy \
  test_asset_director \
  test_buffalo_strategy \
  test_openusd_export \
  test_agentic_paint_service \
  test_paint_service \
  test_reference_projection \
  test_benchmark_arena \
  test_buffalo_runtime \
  test_secure_artifacts \
  test_stage_supervisor \
  test_shape_worker \
  test_shape_parity \
  test_multiview_contract \
  test_multiview_shape_backend \
  test_multiview_shape_worker \
  test_blender_validation_service \
  test_edit_executor \
  test_runtime_certification \
  test_semantic_graph \
  test_derivative_lineage \
  test_adversarial_asset_corpus \
  test_blender_repair_service \
  test_challenger_arena \
  test_human_review \
  test_lod_derivation \
  test_regional_pbr_gate \
  test_review_policy \
  test_cloud_consent \
  test_master_promotion_service \
  test_offline_campaign \
  test_review_gate_evidence \
  test_runtime_probe_evidence \
  test_supply_chain_registry \
  test_audit_asset \
  test_pinned_stage_worker \
  test_pbr_texture_quality_gate \
  test_offline_campaign_repository \
  test_geometry_quality_gate \
  test_offline_corpus_preflight \
  test_canonical_render_evidence \
  test_gltf_validator_gate \
  test_run_offline_campaign \
  test_run_blender_canonical_e2e \
  test_3d_local_orchestrator
