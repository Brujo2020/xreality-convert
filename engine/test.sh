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
  test_benchmark_arena
