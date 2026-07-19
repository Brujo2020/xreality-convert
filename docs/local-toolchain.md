# Toolchain 3D local

La aplicación descubre herramientas locales para informar capacidades disponibles. La
disponibilidad se consulta explícitamente desde el encabezado y no instala, descarga
ni actualiza nada.

## Verificación repetible

```sh
npm run test:tools
```

Este comando ejecuta los contratos del registro Electron y el resumen usado por la
interfaz. Para comprobar además el bundle web:

```sh
npm run test:tools && npm run build:vite
```

## Herramientas incluidas

Las cuatro herramientas siguientes pertenecen al entorno Python embebido. El
registro comprueba su versión mediante ese intérprete local.

| Herramienta | Capacidades informadas |
| --- | --- |
| Trimesh | `inspect_mesh`, `repair_basic`, `convert_stl` |
| PyMeshLab | `inspect_mesh`, `repair_advanced`, `simplify_mesh` |
| xatlas | `unwrap_uv` |
| pygltflib | `inspect_gltf`, `edit_gltf` |

## Herramientas opcionales

Estas herramientas no se incluyen ni se instalan. El registro busca únicamente
ejecutables locales conocidos en `PATH` (y Blender en su ubicación estándar de
macOS). Si no se encuentran, se muestran como `missing` con una pista de instalación;
la aplicación no ofrece un botón de instalación ni un fallback remoto.

| Herramienta | Ejecutable | Capacidades informadas | Fuente oficial |
| --- | --- | --- | --- |
| Khronos glTF Validator | `gltf_validator` | `validate_gltf` | [Khronos glTF Validator](https://github.com/KhronosGroup/glTF-Validator) |
| glTF-Transform | `gltf-transform` | `optimize_gltf`, `convert_gltf` | [CLI oficial de glTF-Transform](https://gltf-transform.dev/cli.html) |
| KTX-Software | `ktx` (preferido), `toktx` (fallback) | `encode_ktx2` | [Khronos KTX-Software](https://github.com/KhronosGroup/KTX-Software) |
| Blender | `blender` | `inspect_scene`, `convert_scene` | [Manual oficial de Blender](https://docs.blender.org/manual/en/latest/) |

## Límites operativos

- El descubrimiento es local: no usa red, gestores de paquetes ni URLs.
- El renderer recibe sólo metadatos públicos: ID, un token de versión numérico
  acotado cuando puede extraerse, capacidades, estado y pista de instalación. Si la
  salida no contiene un token de versión seguro, la versión se omite sin cambiar el
  estado `ready`. No recibe rutas de ejecutables, entorno ni salida cruda de los probes.
- Los estados son cerrados: `ready`, `missing` y `blocked`. Un fallo de probe queda
  `blocked`; una ausencia local queda `missing`.
- `ready` significa que la herramienta se detectó y puede informar su capacidad.
  **No es admisión para ejecutarla contra un asset** y no sustituye la decisión de
  `StageAdmissionReceipt`.
- Este registro no ejecuta conversiones, validaciones, optimizaciones ni codificación
  sobre activos; tampoco cambia el estado de Ollama ni de generación al actualizarse.

## Estado de cierre

Implementado en `main` con estas garantías:

- El inventario se obtiene una vez al iniciar y sólo se repite al pulsar **Comprobar**.
- Los probes tienen timeout, límite de salida y normalización cerrada de estados.
- El renderer no recibe rutas, variables de entorno ni stdout/stderr de procesos.
- El panel admite teclado, Escape, scroll interno y fallback seguro fuera de Electron.
- Los visores STL/GLB y Three.js se cargan bajo demanda; no forman parte del bundle inicial.
- Las ausencias de glTF Validator, glTF-Transform o KTX son capacidades opcionales,
  no tareas pendientes ni errores de la aplicación.

Gate de cierre:

```sh
npm run test:tools
node --check electron/main.js
node --check electron/preload.js
node --check electron/tool-registry.js
npm run build:vite
```
