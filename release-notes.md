# Xreality Convert v1.4.1

## Gate geométrico por destino

- GLB/XR ya no se rechaza por una regla global de `watertight`.
- Productos y orgánicos abiertos continúan como `atención` en perfiles XR; el
  cierre sigue siendo obligatorio para nivel maestro y para exportar STL.
- Si una malla renderizable falla sólo la promoción maestra/sólida, el trabajo
  no se pierde: se entrega degradado y rotulado como GLB/XR no maestro, no STL.
- Ensamblajes como vehículos, grúas, camiones e instalaciones no reciben una
  penalización por estar compuestos por superficies o piezas separadas.
- Todo rechazo geométrico conserva un GLB diagnóstico y un reporte con perfil,
  categoría, contrato, métricas, hitos y estado de memoria.
- Motor local 18 para forzar la actualización segura de este contrato.

Validación: 98 pruebas del motor y 11 del runtime Electron aprobadas.

---

# Xreality Convert v1.4.0

## Buffalo Strategic MLX

- Contrato semántico de piezas y regiones materiales por categoría.
- Gate transaccional que rechaza simplificaciones que pierden componentes.
- Preservación de la malla maestra cuando Low Poly o VR dañan estructura.
- Plan Apple Silicon explícito: Shape y Paint Metal secuenciales, CPU acotada.
- Reporte por carriles con estados `pass`, `reject` y `not_measured`.
- Identidad honesta: arquitectura inspirada en Buffalo; no usa pesos Buffalo
  oficiales ni afirma capacidades todavía no publicadas.
- Conversor GLB → OpenUSD/USDZ con jerarquía, UV, normales y materiales PBR.
- Validación fail-closed mediante `usdchecker --arkit --strict` antes de guardar.
- Botón `Exportar USDZ` para Quick Look y flujos RealityKit en Apple.
- El visor abre el GLB directamente desde disco: evita duplicar archivos grandes
  como Base64 y elimina un crash reproducible del renderer Electron/ANGLE.
- Render PBR ligero para Apple Silicon, sin PMREM ni sombras que compitan por
  memoria gráfica durante la revisión del resultado.
- Arranque del motor protegido también durante la ventana posterior al `spawn`:
  la UI no puede lanzar un segundo Uvicorn mientras el primero importa MLX.

La suite incluye 95 pruebas del motor y 11 pruebas del runtime Electron.

---

# Xreality Convert v1.2.2

## Español

Esta versión deja la distribución de macOS lista para instalarse con identidad visual coherente y firma/notarización validadas.

### Cambios
- Nombre de la app ajustado a `Xreality Convert`
- Icono, favicon y assets de macOS alineados con la nueva identidad
- DMG firmado y notarizado para una instalación más segura en Mac
- Instalador de Hunyuan3D corregido para exigir Python 3.11 o 3.12
- README actualizado y manual bilingüe nuevo con capturas actuales

## English

This release polishes the macOS distribution so it installs with a consistent brand identity and validated signing/notarization.

### Changes
- App name updated to `Xreality Convert`
- macOS icon, favicon, and assets aligned with the new identity
- DMG signed and notarized for safer Mac installation
- Hunyuan3D installer fixed to require Python 3.11 or 3.12
- Updated README and a new bilingual manual with current screenshots
