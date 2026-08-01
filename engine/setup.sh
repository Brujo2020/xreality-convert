#!/bin/zsh
set -euo pipefail

ENGINE_DIR="${0:A:h}"
RUNTIME="$ENGINE_DIR/venv"
SOURCE="$ENGINE_DIR/Hunyuan3D-2.1-mlx"
MARKER="$ENGINE_DIR/.installed"
INSTALL_VERSION="5"

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
    echo "Motor Hunyuan3D Premium ya instalado; reutilizando entorno local."
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

# ============================================
# CORE MLX STACK - OPTIMIZED FOR APPLE SILICON
# ============================================
echo "📦 Instalando MLX y dependencias base..."
python -m pip install torch torchvision torchaudio mlx mlx-lm mlx-arsenal safetensors

echo "📦 Instalando servidor y utilidades..."
python -m pip install Pillow fastapi "uvicorn[standard]" trimesh fast-simplification pymeshlab pygltflib scikit-image PyMCubes scipy huggingface_hub

echo "📦 Instalando procesamiento geométrico avanzado..."
python -m pip install xatlas opencv-python numpy-stl open3d manifold3d pymeshfix

echo "📦 Instalando pipeline PBR profesional..."
python -m pip install diffusers transformers einops omegaconf tqdm rembg onnxruntime kornia basicsr gfpgan realesrgan invisible-watermark

echo "📦 Instalando utilidades premium..."
python -m pip install imageio pyvista

# Optional: BLIP2 for text-to-image multiview (commented for minimal install)
# python -m pip install salesforce-lavis accelerate bitsandbytes

if [[ ! -d "$SOURCE/.git" ]]; then
  git clone --depth 1 https://github.com/dgrauet/Hunyuan3D-2.1-mlx.git "$SOURCE"
fi

echo "$INSTALL_VERSION" > "$MARKER"
echo ""
echo "============================================"
echo "✅ Motor ULTRA instalado exitosamente"
echo "============================================"
echo ""
echo "🎯 OPTIMIZACIONES PARA M5 PRO:"
echo "   ✓ MLX con aceleración Metal nativa"
echo "   ✓ Memory pooling inteligente"
echo "   ✓ Precisión mixta FP16/BF16"
echo "   ✓ Metal Performance Shaders"
echo "   ✓ UV Unwrapping profesional (xatlas)"
echo "   ✓ Texturizado PBR completo"
echo "   ✓ Super-resolución RealESRGAN"
echo "   ✓ Multi-vista AI generativa"
echo ""
echo "🚀 Los pesos se descargarán en la primera conversión."
echo ""
echo "Para iniciar el servidor:"
echo "  source venv/bin/activate"
echo "  python server.py"
echo ""
echo "El servidor estará en: http://127.0.0.1:8765"
