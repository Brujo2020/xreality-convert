# Xreality Convert — Backlog ejecutable

Estados: `[ ]` pendiente, `[~]` en curso, `[x]` completado.

Estado de corte 2026-07-19: versión actual cerrada por aprobación del usuario y QA automatizable. Los pendientes históricos quedan como evolución futura, no como bloqueo de este cierre.

## Cierre 2026-07-19 — versión actual

- [x] Exponer capacidades locales de herramientas 3D.
- [x] Mostrar estado del toolchain local en la app.
- [x] Endurecer detección local de herramientas sin filtrar rutas ejecutables.
- [x] Detectar Python compatible desde app empaquetada.
- [x] Documentar entrega del toolchain local.
- [x] Aprobar diseño de texturizado PBR derivado y editor material en tiempo real.
- [x] Cerrar plan de implementación para texturizado PBR como base de la próxima evolución.
- [x] Dejar textura PBR señalizada como opción lista para el paso final.
- [x] Verificar `npm run test:tools`.
- [x] Verificar `npm run build:vite`.
- [x] Verificar `node --check electron/main.js`.
- [x] Verificar `python3 -m py_compile engine/server.py`.
- [x] Verificar `git diff --check`.

## Evolución futura — P0 Calidad y confiabilidad

- [x] Corregir NaN de sparse marching cubes.
- [x] Eliminar caras degeneradas y duplicadas.
- [x] Detectar y retirar shell envolvente en objetos aislados.
- [x] Añadir categorías iniciales para Imagen → 3D.
- [x] Añadir fondo Automático/Quitar/Conservar.
- [x] Exponer pasos, octree, guidance, padding y caras.
- [x] Añadir preview real de la máscara antes de reconstruir.
- [x] Añadir endpoint `/analyze` para diagnóstico previo.
- [x] Añadir máquina de estados compartida UI/backend.
- [x] Sustituir porcentaje temporal por eventos reales de todas las etapas.
- [x] Añadir cancelación cooperativa del job Python.
- [x] Persistir reporte técnico JSON junto al GLB/STL.
- [x] Implementar quality score por categoría.
- [x] Bloquear exportación cuando el quality gate sea crítico.
- [x] Reparar normales y verificar orientación.
- [x] Añadir validación watertight específica para STL.

## Evolución futura — P0 Orquestación

- [x] Inicio automático de Ollama.
- [x] Inicio automático del servidor Hunyuan.
- [x] Caché persistente de pesos y dependencias.
- [x] Lock de proceso para evitar servidores duplicados.
- [x] Cola local con un job pesado activo.
- [x] Health check con estados degradados diferenciados.
- [x] Reinicio automático con backoff y límite.
- [x] Verificación de espacio libre antes de instalar/generar.
- [ ] Checksum y reparación selectiva de instalación.
- [ ] Logs estructurados por job, etapa, duración y error.
- [ ] Limpieza segura de temporales antiguos.

## Evolución futura — P1 Inteligencia contextual

- [x] Detectar automáticamente categoría y pedir confirmación.
- [x] Detectar múltiples sujetos.
- [x] Detectar sujeto cortado u ocluido.
- [x] Detectar fondo complejo y bajo contraste.
- [x] Detectar orientación y tipo de vista.
- [x] Calificar entrada: Óptima/Procesable/No recomendada.
- [x] Recomendar acciones concretas antes de ejecutar.
- [x] Enriquecer prompts de Crear imagen por categoría.
- [x] Conservar categoría al pasar una imagen generada a 3D.
- [x] Marcar valores manuales como Personalizado.
- [x] Restaurar valores por sección y globalmente.
- [x] Guardar, nombrar y reutilizar presets personales.

## Evolución futura — P1 Casos de uso

- [ ] Animal: test de patas, cola, orejas y cuerpo completo.
- [ ] Persona: test de extremidades, pose y escala.
- [ ] Producto: test de bordes, base, simetría y packaging.
- [ ] Industrial: test de maquinaria y componentes separados.
- [ ] Arquitectura: test de escena y conservación de componentes.
- [ ] WebXR: presupuesto 12K/20K y tamaño de archivo.
- [ ] Quest: presupuesto 20K/50K y auditoría de rendimiento.
- [ ] PC VR: presupuesto 100K y fidelidad.
- [ ] Impresión: manifold, watertight, escala y paredes mínimas.
- [ ] Activo maestro: salida 100K/200K y derivación de LOD.

## Evolución futura — P1 UI/UX

- [x] Crear modo Esencial y modo Experto.
- [x] Mostrar plan de ejecución antes de comenzar.
- [x] Mostrar ruta viva por etapas durante el proceso.
- [x] Añadir comparador original/máscara/preparada.
- [x] Mostrar calidad, tiempo y memoria estimados.
- [x] Añadir estados Recomendado/Modificado/Fuera de rango.
- [x] Añadir auditoría visual posterior con semáforo.
- [x] Hacer responsive a 1024×768, 1440×900 y Retina.
- [x] Completar navegación por teclado y foco visible.
- [x] Respetar `prefers-reduced-motion`.
- [x] Mejorar vacíos y errores con siguiente acción.
- [x] Añadir búsqueda y filtros al historial.

## Evolución futura — P2 Geometría y entrega

- [x] Generar LOD0, LOD1 y LOD2.
- [x] Simplificar conservando bordes duros por categoría.
- [ ] Preservar componentes significativos en arquitectura.
- [ ] Unir o separar componentes de forma configurable.
- [x] Añadir pivot: centro, base o personalizado.
- [x] Añadir orientación Y-up/Z-up.
- [x] Añadir unidades mm/cm/m.
- [x] Validar nombres y metadatos del activo.
- [x] Exportar reporte de auditoría.
- [ ] Verificar GLB en Blender, Three.js y visor macOS.
- [ ] Verificar STL en Blender y slicer.

## Evolución futura — P2 Rendimiento M5 Pro

- [ ] Benchmark Eco/Equilibrado/Máxima calidad.
- [ ] Registrar memoria máxima por etapa.
- [ ] Reutilizar sesión rembg.
- [ ] Evaluar reutilización segura de Hunyuan tras cada job.
- [ ] Evitar concurrencia simultánea Ollama/MLX pesada.
- [ ] Estimar tiempo desde historial local por categoría.
- [ ] Añadir aviso térmico/memoria para sesiones largas.
- [ ] Dividir bundle del visor Three.js mediante carga dinámica.

## QA obligatorio por entrega futura

- [x] `npm run build:vite` sin errores.
- [x] `node --check electron/main.js`.
- [x] `python3 -m py_compile engine/server.py`.
- [x] `git diff --check`.
- [ ] Health de Ollama y Hunyuan.
- [ ] Abrir los tres modos sin errores de consola.
- [ ] Probar un happy path completo por modo.
- [ ] Probar cancelación y recuperación.
- [ ] Confirmar que no se repiten descargas.
- [ ] Confirmar que el historial reabre resultados.
- [ ] Revisar visualmente UI en resoluciones objetivo.

## Definition of Done por tarea

Una tarea solo se marca completada cuando:

1. Tiene implementación y manejo de errores.
2. Incluye evidencia de prueba proporcional al riesgo.
3. No rompe los otros dos flujos.
4. Actualiza documentación o contrato si cambió.
5. Conserva compatibilidad con caché/historial o migra sus datos.
