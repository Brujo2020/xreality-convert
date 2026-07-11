# Xreality Convert — Plan maestro

## Objetivo

Construir una estación local de conversión para artistas 3D y equipos de Xreality que convierta referencias en activos confiables, optimizados y auditables, combinando automatización contextual con control experto.

## Arquitectura objetivo

```text
UI React/Electron
  ├─ Caso de uso y categoría
  ├─ Diagnóstico de entrada
  ├─ Configuración recomendada + overrides
  └─ Progreso, visor, auditoría e historial
          │ IPC validado
Orquestador Electron
  ├─ Lifecycle de Ollama
  ├─ Lifecycle de Hunyuan MLX
  ├─ Caché/versiones/modelos
  ├─ Cola, cancelación y recuperación
  └─ Telemetría local por job
          │ HTTP local
Pipeline Python
  ├─ Preparación/segmentación
  ├─ Reconstrucción Hunyuan3D
  ├─ Limpieza topológica
  ├─ Optimización por destino
  ├─ Quality gate
  └─ GLB/STL + reporte JSON
```

## Fase 0 — Baseline y seguridad

1. Congelar un conjunto de pruebas con animales, personas, productos, máquinas, arquitectura y piezas técnicas.
2. Registrar métricas actuales: tiempo, memoria, caras, componentes, degenerados y aceptación visual.
3. Eliminar cualquier modo mock presentado como resultado real.
4. Versionar runtime, dependencias, pesos y esquema del historial.
5. Añadir logs por job sin guardar contenido sensible de las imágenes.

Salida: baseline reproducible y criterio objetivo de mejora.

## Fase 1 — Orquestador confiable

1. Máquina de estados única: inactivo, preparando, descargando, cargando, procesando, optimizando, validando, completado, cancelado y error.
2. Administrador de procesos para Ollama y Hunyuan con health checks, backoff y prevención de duplicados.
3. Caché de descarga única con checksum, versión y reparación selectiva.
4. Cola de trabajos con un job 3D pesado a la vez.
5. Cancelación real que termina el trabajo y limpia temporales.
6. Progreso por etapas emitido desde backend; estimación basada en historial local por categoría/configuración.
7. Recuperación automática del motor después de un fallo.

Salida: la aplicación se abre y prepara sola, informa siempre su estado y no descarga dos veces.

## Fase 2 — Preparación inteligente de entrada

1. Selector obligatorio/recomendado de categoría.
2. Diagnóstico de resolución, encuadre, sujetos, oclusión y fondo.
3. Fondo Automático/Quitar/Conservar con preview antes/después.
4. Segmentación por categoría y fallback cuando rembg falla.
5. Recorte con padding configurable y prevención de extremidades cortadas.
6. Normalización EXIF, color, canal alpha y tamaño.
7. Recomendaciones accionables y bloqueo solo en errores críticos.

Salida: toda imagen entra limpia y contextualizada, manteniendo control manual.

## Fase 3 — Reconstrucción por categoría

1. Animal: preservar silueta, patas, cola y cabeza; padding orgánico amplio.
2. Persona: cuerpo entero, extremidades separadas y escala humana.
3. Producto: bordes, simetría, base y proporciones.
4. Industrial: componentes principales, volumen técnico y escala operacional.
5. Arquitectura: conservar escena, estructura y componentes significativos.
6. Personalizado: controles neutrales sin supuestos destructivos.
7. Presets Eco, Equilibrado y Máxima calidad dentro de cada categoría.

Salida: parámetros del motor y postproceso específicos para la naturaleza del objeto.

## Fase 4 — Postproceso y quality gate

1. Reparar NaN y artefactos de marching cubes.
2. Eliminar degenerados, duplicados y vértices huérfanos.
3. Detectar shell envolvente frente al sujeto detallado.
4. Seleccionar o conservar componentes según categoría.
5. Simplificar con conservación de silueta/bordes.
6. Corregir normales y orientación.
7. Validar manifold/watertight según destino.
8. Generar LOD0/LOD1/LOD2 para perfiles XR.
9. Rechazar resultados mediocres y sugerir cómo mejorar la entrada.

Salida: ningún artefacto claramente roto aparece como entrega aprobada.

## Fase 5 — Cabina UI/UX profesional

1. Flujo esencial guiado para obtener un resultado correcto rápidamente.
2. Modo experto para editar cada parámetro relevante.
3. Indicadores Recomendado, Modificado y Fuera de rango.
4. Ruta viva del pipeline antes y durante el job.
5. Comparador de referencia, máscara y resultado.
6. Loading circular central, barra por etapas, porcentaje y tiempo estimado.
7. Resumen previo de costo: calidad, tiempo, memoria y salida.
8. Auditoría posterior visual con semáforo técnico.
9. Presets personales guardables, duplicables y restablecibles.
10. Historial filtrable y reapertura completa del contexto.

Salida: interfaz clara para principiantes sin limitar a artistas expertos.

## Fase 6 — Flujos completos

### Crear imagen → Imagen → 3D

1. Categoría en la generación de referencia.
2. Prompt enriquecido para sujeto completo, fondo apropiado y vista útil.
3. Transferencia directa a Imagen → 3D conservando categoría.
4. Diagnóstico y preview de segmentación.
5. Reconstrucción, auditoría y exportación.

### Texto → 3D

1. Formulario técnico opcional: dimensiones, unidad, tolerancias y uso.
2. Generación de código estructurado.
3. Sandbox, validación y reparación limitada.
4. Vista previa, auditoría watertight y STL.

### Imagen → 3D directa

1. Selección/arrastre.
2. Diagnóstico y categoría.
3. Recomendación + retoque manual.
4. Ejecución visible.
5. Auditoría, LOD y exportación.

## Fase 7 — Optimización M5 Pro

1. Medir memoria unificada, latencia y temperatura por preset.
2. Mantener modelos ligeros y sesiones reutilizables cuando sea seguro.
3. Descargar de memoria componentes no usados entre etapas.
4. Evitar paralelismo que compita por Metal.
5. Optimizar imágenes antes del tensor sin degradar la silueta.
6. Estimar duración desde trabajos locales similares.
7. Añadir modo térmico Eco para sesiones largas.

Salida: máximo rendimiento sostenido sin congelar la interfaz ni agotar memoria.

## Fase 8 — Validación y lanzamiento

1. Pruebas unitarias de presets, validadores y máquina de estados.
2. Pruebas de integración IPC → servidor → archivo.
3. Pruebas E2E de los tres flujos.
4. Matriz visual por categoría y preset.
5. Pruebas de cancelar, reiniciar, falta de red, caché dañada y poco disco.
6. Verificación de DMG limpio en un usuario nuevo de macOS.
7. Manual rápido dentro de la app y guía de calidad de referencias.

## Criterios de finalización

- Los tres flujos completan de entrada a exportación.
- El motor se inicia automáticamente y reutiliza la caché.
- Cada operación larga muestra progreso y puede cancelarse.
- Cada categoría aplica parámetros propios y permite overrides.
- El fondo automático toma la decisión esperada y puede forzarse.
- El quality gate bloquea mallas claramente defectuosas.
- GLB/STL exportados se abren en herramientas externas.
- No existen caras degeneradas en resultados aprobados.
- La interfaz funciona en las resoluciones objetivo y es navegable por teclado.

