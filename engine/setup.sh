#!/bin/zsh
set -euo pipefail

ENGINE_DIR="${0:A:h}"
RUNTIME="$ENGINE_DIR/venv"
SOURCE="$ENGINE_DIR/Hunyuan3D-2.1-mlx"
MARKER="$ENGINE_DIR/.installed"
INSTALL_VERSION="3"

if [[ -f "$MARKER" && "$(cat "$MARKER")" == "$INSTALL_VERSION" && -x "$RUNTIME/bin/python" && -d "$SOURCE/.git" ]]; then
  echo "Motor Hunyuan3D ya instalado; reutilizando entorno local."
  exit 0
fi

command -v python3 >/dev/null || { echo "Python 3 no está instalado."; exit 1; }
python3 -m venv "$RUNTIME"
source "$RUNTIME/bin/activate"
python -m pip install --upgrade pip
python -m pip install torch torchvision mlx mlx-arsenal safetensors Pillow fastapi "uvicorn[standard]" trimesh fast-simplification pymeshlab pygltflib scikit-image PyMCubes scipy huggingface_hub xatlas opencv-python diffusers transformers einops omegaconf tqdm rembg onnxruntime

if [[ ! -d "$SOURCE/.git" ]]; then
  git clone --depth 1 https://github.com/dgrauet/Hunyuan3D-2.1-mlx.git "$SOURCE"
fi

echo "$INSTALL_VERSION" > "$MARKER"
echo "Motor Hunyuan3D MLX instalado. Los pesos se descargarán automáticamente en la primera conversión."
