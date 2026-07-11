#!/bin/zsh
set -euo pipefail

ENGINE_DIR="${0:A:h}"
RUNTIME="$ENGINE_DIR/venv"
SOURCE="$ENGINE_DIR/Hunyuan3D-2.1-mlx"
MARKER="$ENGINE_DIR/.installed"
INSTALL_VERSION="4"

python_supports_mlx() {
  local python_bin="$1"
  "$python_bin" - <<'PY'
import sys
major, minor = sys.version_info[:2]
sys.exit(0 if (major, minor) >= (3, 10) else 1)
PY
}

find_python() {
  for candidate in python3.11 python3.12 python3.10; do
    if command -v "$candidate" >/dev/null && python_supports_mlx "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if [[ -f "$MARKER" && "$(cat "$MARKER")" == "$INSTALL_VERSION" && -x "$RUNTIME/bin/python" && -d "$SOURCE/.git" ]]; then
  if python_supports_mlx "$RUNTIME/bin/python"; then
    echo "Motor Hunyuan3D ya instalado; reutilizando entorno local."
    exit 0
  fi
  echo "El entorno Python local es incompatible; se reinstalará con una versión soportada."
  rm -rf "$RUNTIME"
fi

PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  cat <<'EOF'
Python 3.10 o superior no está disponible en este equipo.
Instala Python 3.11 o 3.12 y vuelve a intentar la instalación del motor 3D.
EOF
  exit 1
fi

rm -rf "$RUNTIME"
"$PYTHON_BIN" -m venv "$RUNTIME"
source "$RUNTIME/bin/activate"
python -m pip install --upgrade pip
python -m pip install torch torchvision mlx mlx-arsenal safetensors Pillow fastapi "uvicorn[standard]" trimesh fast-simplification pymeshlab pygltflib scikit-image PyMCubes scipy huggingface_hub xatlas opencv-python diffusers transformers einops omegaconf tqdm rembg onnxruntime

if [[ ! -d "$SOURCE/.git" ]]; then
  git clone --depth 1 https://github.com/dgrauet/Hunyuan3D-2.1-mlx.git "$SOURCE"
fi

echo "$INSTALL_VERSION" > "$MARKER"
echo "Motor Hunyuan3D MLX instalado. Los pesos se descargarán automáticamente en la primera conversión."
