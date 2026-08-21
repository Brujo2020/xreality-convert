# Guía Avanzada y Hacks de Producción: API de Meshy AI (Agosto 2026)

## 🎯 ¿Por qué pagar por la API de Meshy en 2026? (Ventajas Únicas vs. Competencia)

A diferencia de otras soluciones que funcionan como "cajas negras" de un solo pase (como Rodin o Tripo), Meshy ofrece un **ecosistema de API modular y agéntico** diseñado específicamente para pipelines de software, videojuegos y aplicaciones web.

### ⚡ 5 Razones Clave para Elegir la API de Meshy:
1. **Pipeline Asíncrono de 4 Fases Modular (`Preview` -> `Refine` -> `Retexture` -> `Remesh`):** Puedes pausar, inspeccionar o bifurcar el proceso en cualquier fase.
2. **Retexturizado de Mallas Externas (`/v1/retexture`):** Es la única API comercial madura que te permite enviar mallas propias (`.glb`, `.obj`, `.fbx` o CAD) y aplicarles mapas PBR mediante prompts de texto o imágenes de estilo.
3. **De-Lighting Automático (`remove_lighting: true`):** Remueve sombras horneadas en el Albedo para garantizar compatibilidad con iluminación dinámica en Unreal Engine 5, Unity y Three.js.
4. **Remesh Avanzado a Nivel de Código (`topology: "quad"` y `target_polycount`):** Genera mallas cuadrangulares con recuento exacto de polígonos para móvil (Low Poly) o AAA (Mid/High Poly).
5. **Ecosistema MCP (Model Context Protocol):** Integración nativa con Agentes de IA (Cursor, Claude Code, Antigravity) para generación 3D procedimental basada en código.

---

## 🛠️ Los 7 Hacks de Producción para la API de Meshy

### 💡 Hack #1: El Patrón "Cheap Preview Filter" (Ahorro de hasta el 70% de Créditos)
No ejecutes la generación completa de alta resolución a ciegas.
* **Paso 1:** Envía una solicitud `POST /v1/text-to-3d` o `image-to-3d` con `mode: "preview"`. Esto consume un coste mínimo de créditos y genera la geometría base en segundos.
* **Paso 2:** En tu backend, pasa la imagen renderizada 2D del preview a un modelo de visión (p. ej., Gemini / GPT-4o) para evaluar la calidad geométrica o consistencia con el prompt.
* **Paso 3:** Solo si supera el umbral de calidad, llama a `POST /v1/text-to-3d` con `mode: "refine"` pasando el `task_id` del preview.

---

### 💡 Hack #2: Inyección de Texturas PBR en Mallas CAD o Escaneos 3D
¿Tienes modelos 3D sin UVs limpios o escaneos fotogramétricos?
* En lugar de texturizar manualmente en Substance Painter, llama a `POST /v1/retexture`.
* Pasa tu modelo como URL o como **Data URI Base64** (`data:application/octet-stream;base64,...`).
* Proporciona un `image_style_url` con una imagen conceptual del material. Meshy reconstruirá las UVs y generará Albedo, Normal, Roughness y Metallic automáticos.

---

### 💡 Hack #3: Fijación Automática de Pivotes y Escala (`origin_at` & `auto_size`)
Uno de los problemas más molestos al instanciar modelos 3D por código es que el punto pivote quede volando en el centro de la malla.
* Añade `"origin_at": "bottom"` en tu payload JSON. Esto coloca el origen del objeto (0,0,0) exactamente en la base de la malla.
* Activa `"auto_size": true` para que la visión computacional de Meshy escale automáticamente el objeto a dimensiones reales en metros (ideal para escenas AR/VR).

---

### 💡 Hack #4: Exportación Multiformato en Paralelo Sin Coste Adicional
Evita hacer conversiones externas con Python o Blender Server tras descargar el GLB.
* En el payload inicial, especifica:
  ```json
  "target_formats": ["glb", "fbx", "obj", "usdz"]
  ```
* Meshy exportará todos los formatos simultáneamente. Descargas `.usdz` para QuickLook de iOS AR, `.fbx` para Unreal Engine y `.glb` para WebGL/Three.js de una sola llamada.

---

### 💡 Hack #5: Remesh Cuadrangular Programable para Videojuegos
Para personajes o assets orgánicos que requieren deformación o sombras suaves:
* Llama a `POST /v1/remesh`.
* Pasa los parámetros:
  ```json
  {
    "input_task_id": "tu_task_id_anterior",
    "topology": "quad",
    "target_polycount": 5000
  }
  ```
* Obtendrás una malla cuadrangular limpia de exactamente 5.000 polígonos lista para rigging.

---

### 💡 Hack #6: Sustitución de Storage con Base64 Data URIs
Si tu pipeline incluye generación de imágenes con Stable Diffusion / Flux antes de pasar a 3D:
* No necesitas subir la imagen intermedia a un bucket S3/GCS.
* Convierte la imagen a cadena Base64 y pásala directamente:
  ```json
  "image_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
  ```
* Esto reduce la latencia de red y elimina dependencias de almacenamiento temporal.

---

### 💡 Hack #7: Automatización con Webhooks (Bye Bye Polling Loops)
Evita saturar la API consultando el estado cada 2 segundos.
* Configura tus Webhooks en el dashboard de Meshy (hasta 5 endpoints HTTP).
* Tu servidor escuchará un evento `POST` asíncrono con el estado `SUCCEEDED` conteniendo las URLs de descarga de los modelos 3D y mapas PBR.

---

## 💻 Ejemplo de Payload JSON Optimizado (Meshy API v6)

```json
{
  "mode": "preview",
  "ai_model": "meshy-6",
  "prompt": "A futuristic Cyberpunk katana with glowing neon edges, hyperrealistic, game ready",
  "art_style": "realistic",
  "topology": "quad",
  "target_polycount": 12000,
  "origin_at": "bottom",
  "auto_size": true,
  "remove_lighting": true,
  "target_formats": ["glb", "fbx"]
}
```

---

## 📊 Comparativa de Valor: Meshy API vs Otros

| Característica / Endpoint | Meshy API | Tripo API | Rodin API |
| :--- | :--- | :--- | :--- |
| **Pipeline 2 Fases (Preview/Refine)** | ✅ Sí (Ahorro de créditos) | ❌ No | ❌ No |
| **Retexturizado de Mallas Externas** | ✅ Sí (`/v1/retexture`) | ⚠️ Limitado | ❌ No |
| **De-lighting de Texturas** | ✅ Sí (`remove_lighting`) | ❌ No | ⚠️ Básico |
| **Topología Quad Directa** | ✅ Sí (`topology: "quad"`) | ✅ Sí | ❌ Triángulos densos |
| **Integración Servidor MCP** | ✅ Oficial | ⚠️ Comunidad | ❌ No |
| **Webhooks Nativos** | ✅ Hasta 5 Endpoints | ⚠️ Básico | ❌ No |
