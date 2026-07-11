# Xreality Convert — Backlog ejecutable

Estados: `[ ]` pendiente, `[~]` en curso, `[x]` completado.

## P0 — Calidad y confiabilidad

- [x] Corregir NaN de sparse marching cubes.
- [x] Eliminar caras degeneradas y duplicadas.
- [x] Detectar y retirar shell envolvente en objetos aislados.
- [x] Añadir categorías iniciales para Imagen → 3D.
- [x] Añadir fondo Automático/Quitar/Conservar.
- [x] Exponer pasos, octree, guidance, padding y caras.
- [x] Añadir preview real de la máscara antes de reconstruir.
- [x] Añadir endpoint `/analyze` para diagnóstico previo.
- [ ] Añadir máquina de estados compartida UI/backend.
- [ ] Sustituir porcentaje temporal por eventos reales de todas las etapas.
- [x] Añadir cancelación cooperativa del job Python.
- [x] Persistir reporte técnico JSON junto al GLB/STL.
- [x] Implementar quality score por categoría.
- [x] Bloquear exportación cuando el quality gate sea crítico.
- [x] Reparar normales y verificar orientación.
- [x] Añadir validación watertight específica para STL.

## P0 — Orquestación

- [x] Inicio automático de Ollama.
- [x] Inicio automático del servidor Hunyuan.
- [x] Caché persistente de pesos y dependencias.
- [ ] Lock de proceso para evitar servidores duplicados.
- [ ] Cola local con un job pesado activo.
- [ ] Health check con estados degradados diferenciados.
- [ ] Reinicio automático con backoff y límite.
- [ ] Verificación de espacio libre antes de instalar/generar.
- [ ] Checksum y reparación selectiva de instalación.
- [ ] Logs estructurados por job, etapa, duración y error.
- [ ] Limpieza segura de temporales antiguos.

## P1 — Inteligencia contextual

- [ ] Detectar automáticamente categoría y pedir confirmación.
- [ ] Detectar múltiples sujetos.
- [ ] Detectar sujeto cortado u ocluido.
- [ ] Detectar fondo complejo y bajo contraste.
- [ ] Detectar orientación y tipo de vista.
- [ ] Calificar entrada: Óptima/Procesable/No recomendada.
- [ ] Recomendar acciones concretas antes de ejecutar.
- [ ] Enriquecer prompts de Crear imagen por categoría.
- [ ] Conservar categoría al pasar una imagen generada a 3D.
- [ ] Marcar valores manuales como Personalizado.
- [ ] Restaurar valores por sección y globalmente.
- [ ] Guardar, nombrar y reutilizar presets personales.

## P1 — Casos de uso

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

## P1 — UI/UX

- [ ] Crear modo Esencial y modo Experto.
- [ ] Mostrar plan de ejecución antes de comenzar.
- [ ] Mostrar ruta viva por etapas durante el proceso.
- [ ] Añadir comparador original/máscara/preparada.
- [ ] Mostrar calidad, tiempo y memoria estimados.
- [ ] Añadir estados Recomendado/Modificado/Fuera de rango.
- [ ] Añadir auditoría visual posterior con semáforo.
- [ ] Hacer responsive a 1024×768, 1440×900 y Retina.
- [ ] Completar navegación por teclado y foco visible.
- [ ] Respetar `prefers-reduced-motion`.
- [ ] Mejorar vacíos y errores con siguiente acción.
- [ ] Añadir búsqueda y filtros al historial.

## P2 — Geometría y entrega

- [ ] Generar LOD0, LOD1 y LOD2.
- [ ] Simplificar conservando bordes duros por categoría.
- [ ] Preservar componentes significativos en arquitectura.
- [ ] Unir o separar componentes de forma configurable.
- [ ] Añadir pivot: centro, base o personalizado.
- [ ] Añadir orientación Y-up/Z-up.
- [ ] Añadir unidades mm/cm/m.
- [ ] Validar nombres y metadatos del activo.
- [ ] Exportar reporte de auditoría.
- [ ] Verificar GLB en Blender, Three.js y visor macOS.
- [ ] Verificar STL en Blender y slicer.

## P2 — Rendimiento M5 Pro

- [ ] Benchmark Eco/Equilibrado/Máxima calidad.
- [ ] Registrar memoria máxima por etapa.
- [ ] Reutilizar sesión rembg.
- [ ] Evaluar reutilización segura de Hunyuan tras cada job.
- [ ] Evitar concurrencia simultánea Ollama/MLX pesada.
- [ ] Estimar tiempo desde historial local por categoría.
- [ ] Añadir aviso térmico/memoria para sesiones largas.
- [ ] Dividir bundle del visor Three.js mediante carga dinámica.

## QA obligatorio por entrega

- [ ] `npm run build:vite` sin errores.
- [ ] `node --check electron/main.js`.
- [ ] `python3 -m py_compile engine/server.py`.
- [ ] `git diff --check`.
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
