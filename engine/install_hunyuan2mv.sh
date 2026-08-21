#!/bin/zsh
# Download the official Hunyuan3D-2 multi-view Shape weights explicitly.
# This is intentionally opt-in: it is a large, separately licensed candidate
# and is never downloaded by a user generation job.
set -euo pipefail

ENGINE_DIR="${0:A:h}"
WEIGHTS_DIR="${XREALITY_MULTIVIEW_WEIGHTS_DIR:-$ENGINE_DIR/models/Hunyuan3D-2mv}"
REQUIRED_BYTES=$((20 * 1024 * 1024 * 1024))

if ! command -v hf >/dev/null 2>&1; then
  print -u2 "Falta Hugging Face CLI. Instálalo y autentícate antes de continuar."
  exit 2
fi

AVAILABLE_BYTES=$(df -Pk "$ENGINE_DIR" | awk 'NR == 2 { print $4 * 1024 }')
if (( AVAILABLE_BYTES < REQUIRED_BYTES )); then
  print -u2 "Espacio insuficiente: se requieren al menos 20 GiB libres para Hunyuan3D-2mv."
  exit 3
fi

print "Descargando tencent/Hunyuan3D-2mv en: $WEIGHTS_DIR"
print "Debes haber aceptado su licencia y ejecutado: hf auth login"
env -u HF_HUB_OFFLINE -u TRANSFORMERS_OFFLINE \
  hf download tencent/Hunyuan3D-2mv --local-dir "$WEIGHTS_DIR"

print "Pesos descargados. Configura antes de habilitar la ruta experimental:"
print "  export XREALITY_MULTIVIEW_WEIGHTS_DIR='$WEIGHTS_DIR'"
print "  export XREALITY_MULTIVIEW_SHAPE_WORKER=1"
