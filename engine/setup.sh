#!/bin/zsh
set -euo pipefail

ENGINE_DIR="${0:A:h}"
RUNTIME="$ENGINE_DIR/venv"
SOURCE="$ENGINE_DIR/Hunyuan3D-2.1-mlx"
AGENTIC_SOURCE="$ENGINE_DIR/AgenticVibes-Hunyuan3D-Paint"
AGENTIC_RASTERIZER="$AGENTIC_SOURCE/hy3dpaint/custom_rasterizer"
MARKER="$ENGINE_DIR/.installed"
LOCKFILE="$ENGINE_DIR/requirements-macos.lock"
INSTALL_VERSION="21"
SOURCE_REVISION="xreality-buffalo-mlx-openusd-watertight-v3-memfix"
SOURCE_MARKER="$ENGINE_DIR/.source-version"
# The installer creates a Python environment and compiled rasterizer before
# model weights are fetched on first use. Reserve enough room for that local
# work instead of leaving a half-created runtime on a full volume.
MIN_INSTALL_FREE_KIB=$((20 * 1024 * 1024))

ensure_install_space() {
  local free_kib
  free_kib="$(/bin/df -Pk "$ENGINE_DIR" | /usr/bin/awk 'NR == 2 { print $4; exit }')"
  if [[ ! "$free_kib" =~ '^[0-9]+$' ]]; then
    echo "No se pudo comprobar el espacio libre para instalar el motor 3D."
    return 1
  fi
  if (( free_kib < MIN_INSTALL_FREE_KIB )); then
    echo "Espacio insuficiente para instalar el motor 3D: se requieren al menos 20 GB libres."
    return 1
  fi
}

python_supports_mlx() {
  local python_bin="$1"
  "$python_bin" - <<'PY'
import sys
major, minor = sys.version_info[:2]
sys.exit(0 if (major, minor) in ((3, 11), (3, 12)) else 1)
PY
}

find_python() {
  local candidates=(
    "${XREALITY_PYTHON:-}"
    /opt/homebrew/bin/python3.11
    /opt/homebrew/bin/python3.12
    /usr/local/bin/python3.11
    /usr/local/bin/python3.12
    "$HOME/.local/bin/python3.11"
    "$HOME/.local/bin/python3.12"
    python3.11
    python3.12
    python3.10
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    if { [[ "$candidate" == */* ]] && [[ -x "$candidate" ]]; } || command -v "$candidate" >/dev/null; then
      if ! python_supports_mlx "$candidate"; then
        continue
      fi
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [[ "${1:-}" == "--find-python" ]]; then
  find_python
  exit $?
fi

if [[ -f "$MARKER" && "$(cat "$MARKER")" == "$INSTALL_VERSION" && -f "$SOURCE_MARKER" && "$(cat "$SOURCE_MARKER")" == "$SOURCE_REVISION" && -x "$RUNTIME/bin/python" ]]; then
  if python_supports_mlx "$RUNTIME/bin/python"; then
    echo "Motor Hunyuan3D Premium ya instalado; reutilizando entorno local."
    exit 0
  fi
  echo "El entorno Python local es incompatible; se reinstalará con una versión soportada."
  rm -rf "$RUNTIME"
fi

ensure_install_space

if [[ -x "$RUNTIME/bin/python" ]] && ! python_supports_mlx "$RUNTIME/bin/python"; then
  echo "El entorno Python local es incompatible; se reinstalará con una versión soportada."
  rm -rf "$RUNTIME"
fi

if [[ -d "$RUNTIME" && ! -x "$RUNTIME/bin/python" ]]; then
  echo "El entorno Python local está incompleto; se recreará sin tocar modelos ni resultados."
  rm -rf "$RUNTIME"
fi

if [[ ! -x "$RUNTIME/bin/python" ]]; then
  PYTHON_BIN="$(find_python || true)"
  if [[ -z "$PYTHON_BIN" ]]; then
    cat <<'EOF'
Python 3.10 o superior no está disponible en este equipo.
Instala Python 3.11 o 3.12 y vuelve a intentar la instalación del motor 3D.
EOF
    exit 1
  fi
  "$PYTHON_BIN" -m venv "$RUNTIME"
fi

source "$RUNTIME/bin/activate"
if [[ ! -f "$LOCKFILE" ]]; then
  echo "No se encontró el lock de dependencias: $LOCKFILE"
  exit 1
fi
echo "📦 Instalando el runtime macOS reproducible..."
python -m pip install --prefer-binary --disable-pip-version-check -r "$LOCKFILE"

if [[ ! -f "$SOURCE/hy3dshape/hy3dshape/pipeline_mlx.py" || ! -f "$SOURCE/hy3dpaint/textureGenPipeline_mlx.py" ]]; then
  echo "La fuente Shape/Paint no está incluida. Reinstala Xreality Convert desde el DMG."
  exit 1
fi

if [[ ! -f "$AGENTIC_SOURCE/hy3dpaint/mlx/hybrid_unet.py" ]]; then
  echo "La fuente AgenticVibes Paint no está incluida. Reinstala Xreality Convert desde el DMG."
  exit 1
fi

if ! PYTHONPATH="$AGENTIC_RASTERIZER" python - <<'PY'
import torch
import custom_rasterizer_kernel
PY
then
  echo "🔨 Compilando rasterizador AgenticVibes para este Python/Apple Silicon..."
  (
    cd "$AGENTIC_RASTERIZER"
    MAX_JOBS=4 python setup.py build_ext --inplace
  )
fi

echo "🔎 Validando contrato MLX secuencial..."
PYTHONPATH="$SOURCE:$SOURCE/hy3dpaint" python - <<'PY'
import inspect
from hy3dshape.hy3dshape.pipeline_mlx import ShapePipeline

constructor = inspect.signature(ShapePipeline.__init__).parameters
loader = inspect.signature(ShapePipeline.from_pretrained).parameters
if "dit_loader" not in constructor or "vae_loader" not in constructor:
    raise RuntimeError("La fuente Shape no libera modelos entre etapas")
if "torch_dtype" in loader:
    raise RuntimeError("Contrato Shape MLX incompatible")
PY

echo "🔎 Validando Paint AgenticVibes sin UNet PyTorch duplicado..."
PYTHONPATH="$AGENTIC_SOURCE:$AGENTIC_RASTERIZER" python - <<'PY'
from pathlib import Path

source = Path(__import__("hy3dpaint.mlx.hybrid_unet", fromlist=["__file__"]).__file__)
text = source.read_text(encoding="utf-8")
if "_MLXUNetProxy" not in text or "duplicate Torch UNet released" not in text:
    raise RuntimeError("AgenticVibes no libera el UNet PyTorch duplicado")
PY

echo "$SOURCE_REVISION" > "$SOURCE_MARKER"
echo "$INSTALL_VERSION" > "$MARKER"
echo ""
echo "============================================"
echo "✅ Motor local instalado exitosamente"
echo "============================================"
echo ""
echo "🎯 RUNTIME MAC:"
echo "   ✓ MLX con aceleración Metal nativa"
echo "   ✓ Dependencias y fuente fijadas"
echo "   ✓ Shape y Paint aislados en memoria unificada"
echo "   ✓ Texturizado Hunyuan Paint de seis vistas"
echo "   ✓ AgenticVibes MLX con UNet PyTorch duplicado liberado"
echo "   ✓ Buffalo Strategic MLX: partes, preservación y gates transaccionales"
echo ""
echo "🚀 Los pesos se descargarán en la primera conversión."
echo ""
echo "Para iniciar el servidor:"
echo "  source venv/bin/activate"
echo "  python server.py"
echo ""
echo "El servidor estará en: http://127.0.0.1:8765"
