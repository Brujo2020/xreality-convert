# Xreality Convert — Requerimientos de producto

## 1. Propósito

Xreality Convert debe transformar imágenes o descripciones en activos 3D locales, editables y preparados para XR, digital twins, WebXR, VR, AR móvil e impresión 3D. El producto está dirigido a artistas 3D, diseñadores industriales y equipos de spatial computing.

## 2. Principios obligatorios

1. Local-first: modelos, imágenes y geometría permanecen en el Mac salvo acción explícita.
2. Descarga única: cada modelo o dependencia se instala una sola vez y se reutiliza desde caché.
3. Visibilidad: toda operación larga muestra etapa, porcentaje, tiempo transcurrido y estimación restante.
4. Presets + control: el sistema recomienda configuraciones, pero todos los parámetros relevantes pueden ajustarse manualmente.
5. Calidad antes que apariencia: una malla defectuosa se rechaza con instrucciones concretas; nunca se presenta como resultado válido.
6. Contexto explícito: Imagen → 3D exige o recomienda una categoría antes de procesar.
7. Resultado reproducible: se guardan entrada, categoría, preset, parámetros, modelo, versión y métricas.

## 3. Flujos principales

### RF-01 Crear imagen

- Seleccionar un modelo visual instalado en Ollama.
- Instalar FLUX.2 Klein una sola vez si falta.
- Crear referencias adecuadas para reconstrucción 3D.
- Elegir categoría antes de generar para enriquecer automáticamente el prompt.
- Configurar tamaño, pasos, semilla, fondo, vista y calidad.
- Usar la imagen generada directamente como entrada de Imagen → 3D.

### RF-02 Texto → 3D

- Crear geometría paramétrica mediante un modelo de código local.
- Priorizar piezas técnicas, soportes, volúmenes simples y objetos imprimibles.
- Permitir dimensiones, tolerancias, unidades, paredes mínimas y base plana.
- Validar sintaxis, caras, dimensiones, manifold y watertight antes de entregar.
- Exportar STL y conservar código fuente paramétrico.

### RF-03 Imagen → 3D

- Aceptar PNG, JPG y WEBP mediante selector o drag-and-drop.
- Categorías: animal, persona, producto, industrial, arquitectura y personalizado.
- Aplicar configuraciones diferentes según categoría.
- Fondo con tres modos: Automático, Quitar y Conservar.
- En Automático, quitar fondo para sujetos aislables y conservarlo para arquitectura/escenas.
- Permitir ajustar pasos, octree, guidance, margen, escala, caras y perfil final.
- Preprocesar: orientación, transparencia, segmentación, recorte, centrado y padding.
- Reconstruir con Hunyuan3D MLX local.
- Limpiar componentes, shells, caras degeneradas, duplicadas y vértices huérfanos.
- Simplificar hasta el presupuesto objetivo sin destruir la silueta.
- Rechazar resultados por debajo del umbral de calidad.
- Exportar GLB y convertir a STL cuando corresponda.

## 4. Casos de uso

| Caso | Categoría inicial | Salida | Prioridad |
|---|---|---|---|
| Activo industrial | Industrial | GLB XR | Fidelidad dimensional y silueta |
| Producto comercial | Producto | GLB/WebXR | Apariencia y bajo peso |
| Animal o personaje | Animal/Persona | GLB maestro | Anatomía y componentes orgánicos |
| Móvil y WebXR | Producto/Custom | GLB 12K–20K | FPS y descarga rápida |
| Meta Quest | Variable | GLB 20K–50K | Rendimiento autónomo |
| PC VR | Variable | GLB 50K–100K | Fidelidad visual |
| Impresión 3D | Industrial/Custom | STL | Watertight y dimensiones |
| Arquitectura | Arquitectura | GLB escena | Estructura y escala |
| Activo maestro | Variable | GLB 100K–200K | Máximo detalle reutilizable |

## 5. Orquestación inteligente

### RF-04 Diagnóstico previo

Antes de procesar, el sistema debe evaluar:

- Resolución y relación de aspecto.
- Cantidad estimada de sujetos.
- Sujeto completo o cortado.
- Contraste sujeto/fondo.
- Oclusiones y elementos delante.
- Vista frontal, lateral o tres cuartos.
- Presencia de transparencia.
- Compatibilidad entre categoría, imagen y perfil de salida.

Debe mostrar un estado: Óptima, Procesable con ajustes o No recomendada, acompañado de acciones concretas.

### RF-05 Plan de ejecución visible

Antes de iniciar se debe resumir:

`Entrada → preparación → motor → limpieza → optimización → auditoría → exportación`

La ruta debe actualizarse durante el proceso y marcar etapas completadas, activa, pendientes o fallidas.

### RF-06 Recomendaciones no destructivas

- Cambiar categoría aplica un preset inicial.
- Modificar manualmente un valor lo marca como Personalizado.
- El sistema no debe sobrescribir cambios manuales silenciosamente.
- Debe existir “Restaurar recomendación” por sección y global.
- Debe poder guardarse un preset propio.

## 6. Parámetros editables

- Categoría y caso de uso.
- Modo de fondo.
- Margen del sujeto.
- Pasos de reconstrucción.
- Resolución octree.
- Guidance/fidelidad.
- Presupuesto de caras.
- Escala y unidad.
- Perfil de entrega.
- Textura y resolución de textura.
- Tamaño STL.
- Simplificación y conservación de bordes.
- Limpieza de componentes.
- Semilla, dimensiones y pasos de imagen.

## 7. Calidad y auditoría

### RF-07 Métricas mínimas

- Caras y vértices.
- Componentes conectados.
- Caras degeneradas y duplicadas.
- Bordes abiertos.
- Watertight.
- Dimensiones y escala.
- Presupuesto frente al perfil.
- Tiempo total y por etapa.

### RF-08 Quality gate

Un resultado no puede declararse listo si:

- Contiene caras degeneradas relevantes.
- La geometría útil está bajo el mínimo de la categoría.
- El componente principal representa una fracción insuficiente del modelo.
- No existe archivo exportable.
- Excede el presupuesto sin advertencia.
- Es STL y no cumple el criterio de impresión seleccionado.

## 8. Experiencia de usuario

- Interfaz completa en español.
- Fondo azul oscuro NTT DATA, vidrio controlado, cian como señal operativa.
- Jerarquía: Caso → Entrada → Contexto → Destino → Ajustes → Ejecutar.
- Modo esencial y modo experto.
- Loading circular grande en el visor y progreso persistente en el panel.
- Porcentaje real cuando el backend informa etapa; aproximado claramente identificado cuando no.
- Cancelación visible y segura.
- Errores con causa y siguiente acción.
- Historial local con miniatura, tipo, parámetros y reapertura.
- Accesibilidad por teclado, foco visible y reducción de movimiento.

## 9. Operación local

- La aplicación inicia Ollama si no está abierto.
- Verifica puerto y salud antes de usarlo.
- Inicia Hunyuan3D automáticamente cuando se entra al flujo correspondiente.
- Instala dependencias faltantes con versión y marcador de instalación.
- Conserva pesos en caché entre sesiones y actualizaciones.
- Evita procesos duplicados y libera procesos hijos al cerrar.
- Muestra estado separado de Ollama, modelo visual, Hunyuan y almacenamiento.

## 10. MacBook Pro M5 Pro

- Usar Apple MLX y Metal cuando estén disponibles.
- Evitar copias innecesarias CPU↔GPU y recargas del modelo.
- Reutilizar sesiones de segmentación.
- Limitar concurrencia para evitar presión de memoria.
- Permitir perfiles Eco, Equilibrado y Máxima calidad.
- Advertir memoria estimada antes de trabajos pesados.
- Mantener interfaz fluida mientras el backend procesa.

## 11. Requerimientos no funcionales

- RNF-01: inicio de interfaz menor a 3 s sin cargar pesos pesados.
- RNF-02: respuesta visual a interacción menor a 100 ms.
- RNF-03: progreso actualizado al menos cada 1 s.
- RNF-04: cero descargas repetidas con versión sin cambios.
- RNF-05: cero caras degeneradas en una entrega aprobada.
- RNF-06: recuperación tras cancelar o fallar sin reiniciar la aplicación.
- RNF-07: historial resistente a entradas corruptas.
- RNF-08: validación en 1024×768, 1440×900 y pantalla Retina.
- RNF-09: no exponer shell, Python o rutas internas innecesarias al usuario.
- RNF-10: logs locales estructurados por job y etapa.

## 12. Fuera de alcance inicial

- Rigging automático profesional.
- Animación corporal completa.
- Retopología manual equivalente a Blender/Maya.
- Reconstrucción fotogramétrica multivista de precisión métrica.
- Generación PBR completa si el backend MLX utilizado no la soporta realmente.

