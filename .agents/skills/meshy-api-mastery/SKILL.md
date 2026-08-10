---
name: meshy-api-mastery
description: Guía de nivel experto para dominar la API de Meshy v6, su esquema de precios, economía de créditos, endpoints REST, integración agéntica (MCP) y optimización de costes con la estrategia Cheap Preview Filter.
---

# Meshy API Mastery & Credit Economics Skill (2026)

## 📌 Visión General de la API de Meshy (v6)

Meshy.ai proporciona una API REST asíncrona para la generación, texturizado y retopología 3D de calidad de producción. Los clientes envían tareas `POST`, reciben un `task_id` y realizan polling `GET` o escuchan Webhooks hasta el estado `SUCCEEDED`.

---

## 💰 Matriz de Precios y Economía de Créditos

| Acción / Endpoint | Modo / Configuración | Coste en Créditos | Notas de Optimización |
| :--- | :--- | :--- | :--- |
| **Text to 3D** | `mode: "preview"` | **5 Créditos** | Genera malla borrador rápida sin PBR denso. |
| **Text to 3D** | `mode: "refine"` | **20 Créditos** | Requiere `preview_task_id`. Genera mallas 8K con PBR. |
| **Image to 3D** | `mode: "preview"` | **5 Créditos** | Reconstrucción rápida de silueta a partir de 2D. |
| **Image to 3D** | `mode: "refine"` | **20 Créditos** | Refinado PBR completo. |
| **Retexture** | `/v1/retexture` | **10 Créditos** | Aplica PBR a mallas subidas (`.glb`, `.obj`, `.fbx`). |
| **Remesh** | `/v1/remesh` | **5 Créditos** | Convierte mallas caóticas a `topology: "quad"` limpia. |

### 💡 La Estrategia "Cheap Preview Filter" (Ahorro del 70-80% en Créditos)
En lugar de lanzar 4 generaciones completas de 25 créditos cada una (Total = 100 créditos):
1. Lanzas 4 borradores con `mode: "preview"` (Total = $4 \times 5 = 20$ créditos).
2. Evalúas la imagen 2D devuelta con un modelo de visión ligero (Gemini / GPT-4o).
3. Seleccionas la 1 mejor variante y ejecutas `mode: "refine"` solo en ella ($20$ créditos).
4. **Gasto Total:** 40 créditos en lugar de 100 (**Ahorro directo del 60% al 80%**).

---

## 🌐 Endpoints Principales & Schemas REST

### 1. Generación Texto a 3D (`POST /v1/text-to-3d`)
```json
{
  "mode": "preview",
  "prompt": "Cyberpunk helmet, clean quads, game ready",
  "art_style": "realistic",
  "topology": "quad",
  "target_polycount": 12000,
  "origin_at": "bottom",
  "auto_size": true,
  "remove_lighting": true,
  "target_formats": ["glb", "usdz", "fbx"]
}
```

### 2. Retexturizado de Mallas Externas (`POST /v1/retexture`)
```json
{
  "model_url": "https://tuservidor.com/mi_malla.glb",
  "text_style_prompt": "Industrial worn rusted iron with yellow hazard stripes",
  "remove_lighting": true
}
```

### 3. Remesh Cuadrangular Optimizado (`POST /v1/remesh`)
```json
{
  "input_task_id": "018e3a2b-7c1d-7000-8000-123456789abc",
  "topology": "quad",
  "target_polycount": 5000
}
```

---

## 🦖 Integración con NVIDIA Axolotl3D (Unified 3D Framework)

NVIDIA Axolotl3D une cuatro tareas fundamentales en un solo modelo:
1. **Multi-View Synthesis:** Reconstrucción a partir de múltiples ángulos.
2. **Occlusion Handling (Amodal 3D):** Inferencia de partes ocultas/traseras no visibles en la foto.
3. **Geometry-Control:** Control explícito sobre la topología y recuento de caras.
4. **3D Editing:** Modificación semántica localizada de partes.

*En nuestro pipeline agéntico:*
- Usamos **Meshy v6** como motor principal de texturizado y retopología en la nube.
- Usamos la teoría de **Axolotl3D / Hunyuan3D-Buffalo 1.0** para la inferencia amodal y edición localizada por partes.
