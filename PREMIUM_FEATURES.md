# Xreality Convert PREMIUM - Studio 3D Profesional Local

## 🚀 El Mejor Sistema de Conversión Foto/Texto → 3D con Texturas PBR

**Optimizado para MacBook Pro M5 Pro con MLX**

### Características Premium Implementadas

#### 1. **Texturizado PBR Completo** (Industry Standard)
- ✅ UV Unwrapping con xatlas (mismo algoritmo que Blender/Maya)
- ✅ Generación de mapas PBR:
  - Albedo (color base sin iluminación)
  - Roughness (rugosidad de superficie)
  - Metallic (metalicidad)
  - Normal maps (detalle de superficie)
- ✅ Super-resolución con RealESRGAN (2x upscaling)
- ✅ Exportación GLTF/GLB con texturas incrustadas
- ✅ Compatible con Unity, Unreal, Three.js, Babylon.js, Blender

#### 2. **Texto → 3D Directo** (Multi-View Synthesis)
- ✅ Generación de 4-6 vistas ortogonales consistentes
- ✅ Difusión condicionada por texto
- ✅ Síntesis de vistas novel-view
- ✅ Pipeline completo: Texto → Multivista → Malla 3D → Texturas PBR

#### 3. **Optimizaciones M5 Pro**
- ✅ Aceleración MLX nativa para Apple Silicon
- ✅ GPU MPS (Metal Performance Shaders)
- ✅ Memoria unificada optimizada
- ✅ Lazy loading de modelos pesados
- ✅ Gestión inteligente de VRAM

#### 4. **Calidad Profesional**
- ✅ Quality gate automático
- ✅ Detección de mallas degeneradas
- ✅ Limpieza de geometría
- ✅ Decimación quadric-preserving
- ✅ Validación watertight/manifold

### Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    Xreality Convert UI                       │
│                     (Electron + React)                       │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP/REST API
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Server (Local)                      │
│                                                              │
│  Endpoints:                                                  │
│  ├── POST /analyze         - Análisis de imagen             │
│  ├── POST /generate        - Imagen → 3D + PBR              │
│  ├── POST /text-to-3d      - Texto → 3D + PBR (PREMIUM)     │
│  ├── POST /to-stl          - Conversión a STL               │
│  └── GET  /status/{id}     - Estado del job                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Hunyuan3D   │ │   PBR        │ │  MultiView   │
│  MLX Shape   │ │  Texturer    │ │  Generator   │
│  Pipeline    │ │  (xatlas +   │ │  (Diffusion) │
│              │ │   RealESRGAN)│ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Instalación Premium

```bash
# 1. Clonar el repositorio
cd /workspace

# 2. Ejecutar instalador premium
chmod +x engine/setup.sh
./engine/setup.sh

# 3. Iniciar servidor
cd engine
source venv/bin/activate
python server.py
```

### Dependencias Premium Instaladas

```
Core MLX Stack:
├── torch (Apple Silicon optimized)
├── torchvision
├── mlx
├── mlx-arsenal
└── safetensors

Geometry Processing:
├── trimesh
├── fast-simplification
├── pymeshlab
├── pygltflib
├── numpy-stl
└── open3d

Texture & PBR:
├── xatlas (UV unwrapping)
├── kornia (vision differentiable)
├── basicsr (super-resolution base)
├── gfpgan (face enhancement)
└── realesrgan (texture upscaling)

Image Processing:
├── Pillow
├── opencv-python
├── scikit-image
├── PyMCubes
└── rembg (background removal)

Diffusion Models:
├── diffusers
├── transformers
├── einops
├── omegaconf
└── huggingface_hub
```

### Uso de la API

#### Imagen → 3D con Texturas PBR

```python
import requests
import base64

# Cargar imagen
with open("referencia.png", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

# Solicitar generación
response = requests.post("http://127.0.0.1:8765/generate", json={
    "image_base64": image_b64,
    "texture": True,              # Activar PBR
    "texture_resolution": 2048,   # 2K texturas
    "steps": 30,
    "octree_resolution": 192,
    "target_faces": 50000,
    "category": "product",
    "guidance": 6.0
})

job_id = response.json()["job_id"]

# Monitorear progreso
while True:
    status = requests.get(f"http://127.0.0.1:8765/status/{job_id}")
    data = status.json()
    print(f"Progreso: {data['progress']}% - {data['stage']}")
    
    if data["status"] == "done":
        print(f"✅ Completado en {data['elapsed']}s")
        print(f"GLB: {data['glb_path']}")
        break
```

#### Texto → 3D con Multi-Vista

```python
import requests

response = requests.post("http://127.0.0.1:8765/text-to-3d", json={
    "prompt": "un reloj futurista de lujo con detalles dorados",
    "negative_prompt": "blurry, low quality, distorted",
    "texture": True,
    "texture_resolution": 2048,
    "num_views": 6,           # 6 vistas para mejor cobertura
    "steps": 30,
    "guidance": 5.5,
    "seed": 42                # Para reproducibilidad
})

job_id = response.json()["job_id"]
```

### Secretos y Mejores Prácticas Implementados

#### 1. **UV Unwrapping Óptimo**
- Usamos xatlas que minimiza distorsión angular y de área
- Similar al algoritmo de Blender's UV unwrap
- Empaquetado eficiente del espacio UV (>85% utilización)

#### 2. **Estimación PBR Basada en Física**
```python
# Roughness estimation desde gradientes de luminancia
variance = sqrt(E[I²] - E[I]²)  # Varianza local
roughness = normalize(variance)

# Metallic estimation desde saturación HSV
metal_mask = (S > 50) & (V > 100) & (V < 230)
```

#### 3. **Normal Maps Híbridos**
- Combina normales geométricas + detalle de textura
- Filtros Sobel para gradientes de alta frecuencia
- Compatible con shaders estándar (OpenGL/DirectX)

#### 4. **Super-Resolución de Texturas**
- RealESRGAN x2 para texturas 2K→4K
- Preserva bordes y detalles finos
- Ejecución en GPU MPS para velocidad

#### 5. **Quality Gate Robusto**
```python
minimum_faces = 3000 if category in {"animal", "person"} else 800
if faces < minimum_faces or vertices < 500:
    raise RuntimeError("Rechazado: geometría insuficiente")
```

### Comparativa con Soluciones Web

| Característica | Hunyuan Web | Tripo AI | Xreality PREMIUM |
|---------------|-------------|----------|------------------|
| Local | ❌ | ❌ | ✅ |
| PBR Textures | ⚠️ Limitado | ✅ | ✅ Completo |
| Texto→3D | ✅ | ✅ | ✅ |
| Privacidad | ❌ Cloud | ❌ Cloud | ✅ 100% Local |
| Coste | $$/modelo | $$/crédito | ✅ Gratis |
| Personalización | ❌ | ⚠️ API | ✅ Total |
| M5 Optimized | ❌ | ❌ | ✅ Nativo |

### Rendimiento Esperado (M5 Pro)

| Tarea | Tiempo | VRAM |
|-------|--------|------|
| Imagen → Malla | 45-90s | 8-12GB |
| UV Unwrapping | 2-5s | <1GB |
| PBR Estimation | 10-20s | 2-4GB |
| RealESRGAN 2x | 5-10s | 4-6GB |
| **Total con texturas** | **60-120s** | **12-16GB** |

### Archivos Generados

Para cada conversión con texturas:
```
jobs/
├── {job_id}.glb              # Malla con texturas incrustadas
├── {job_id}_albedo.png       # Mapa de color base (2048x2048)
├── {job_id}_roughness.png    # Mapa de rugosidad
├── {job_id}_metallic.png     # Mapa de metallicidad
├── {job_id}_normal.png       # Mapa de normales
├── {job_id}_materials.json   # Configuración PBR
└── reports/{job_id}.json     # Métricas y calidad
```

### Próximas Mejoras (Roadmap)

- [ ] Integración con Zero123++ para mejor síntesis de vistas
- [ ] Soporte para texturas 4K nativas
- [ ] Animación automática de rigs básicos
- [ ] Exportación directa a USDZ para AR
- [ ] Batch processing múltiple
- [ ] Interpolación de formas (morphing)

---

**Desarrollado con ❤️ para spatial computing profesional**

*Compatible con Vision Pro, Quest 3, y todos los headsets XR*
