# Buffalo Strategic MLX

## Qué es

Arquitectura local inspirada por la tesis de Hunyuan3D-Buffalo 1.0: la
comprensión de estructura y partes debe condicionar la generación y edición
3D. Xreality adopta esa estrategia sobre su backend Shape/Paint MLX existente.

No incluye ni afirma usar código o pesos oficiales de Buffalo. A la fecha de
diseño, el proyecto oficial indica que el código se publicará posteriormente.

Referencia primaria:
https://arxiv.org/html/2608.02711

## Contrato ejecutable

Cada trabajo produce cinco contratos independientes:

1. **Entrada:** vistas reales, categoría, fondo y evidencia disponible.
2. **Partes:** inventario esperado, cardinalidad, piezas críticas y elementos
   delgados por categoría.
3. **Geometría:** límites de caras, componentes, winding y watertightness según
   el tipo de activo.
4. **Material:** regiones esperadas, mapas PBR y extensiones glTF requeridas.
5. **Apple:** plan de ejecución según memoria y núcleos del Mac.

Las piezas o regiones no observadas permanecen `not_measured`; una vista
sintética nunca se convierte en evidencia real.

## Flujo Apple Silicon

```text
contrato semántico ─┐
preparar referencia ├─ ventana CPU acotada
cargar Shape MLX ───┘
        ↓
Shape MLX (Metal exclusivo)
        ↓
liberar pesos + limpiar caché
        ↓
huella de ensamblaje → simplificación candidata → gate de preservación
        ↓                                      ↘ rechazo: conservar maestro
Paint MLX (Metal exclusivo)
        ↓
PBR → GLB → reporte Buffalo → USDZ/RealityKit (opcional)
```

Shape y Paint nunca se ejecutan simultáneamente. Los núcleos CPU sólo se usan
en paralelo para preparación y validaciones acotadas.

## Mejora sobre Buffalo 1.0

- La preservación no depende únicamente de cajas 3D: compara componentes,
  balance de áreas y extensión global antes y después de simplificar.
- La simplificación es transaccional. Un candidato que pierde estructura no
  reemplaza la malla aceptada.
- El resultado no se autocertifica con un VLM; gates deterministas pueden
  rechazarlo y el nivel maestro exige evidencia adicional.
- El contrato incluye materiales y GLB/PBR, área que Buffalo 1.0 reconoce como
  trabajo futuro.
- El plan es consciente de memoria unificada y mantiene un único consumidor
  Metal pesado a la vez.

## Bonus OpenUSD para Apple

La entrega GLB puede convertirse a un paquete `.usdz` autocontenido. El
exportador preserva jerarquía de piezas, UV, normales, factores y texturas
UsdPreviewSurface (color base, metal/rugosidad, normal y emisión), además del
manifiesto Buffalo y las huellas SHA-256.

La conversión no se aprueba por existencia del archivo: `usdzip` normaliza el
paquete para RealityKit y `usdchecker --arkit --strict` debe aprobarlo antes de
que la interfaz permita guardarlo. El archivo resultante sirve como formato
OpenUSD portable para Quick Look y flujos RealityKit.

## Lo que aún no es

- No es un modelo entrenado de comprensión 3D ni un port de pesos Buffalo.
- No identifica por sí solo qué componente geométrico corresponde a cada
  nombre semántico; ese carril se reporta `not_measured` hasta disponer de
  evidencia multivista, anotación humana o un modelo local validado.
- No promete una mejora porcentual sin ejecutar el mismo corpus antes y
  después. Las métricas válidas son pérdida de componentes, cumplimiento de
  presupuesto, calidad GLB/PBR, memoria pico y tiempo por etapa.

Referencias OpenUSD:

- https://openusd.org/dev/spec_usdpreviewsurface.html
- https://openusd.org/dev/api/class_usd_geom_mesh.html
- https://developer.apple.com/augmented-reality/quick-look/
