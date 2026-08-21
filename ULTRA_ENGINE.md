# Xreality Convert — motor local para macOS

## Alcance comprobable

Xreality Convert transforma una referencia de imagen en una malla con
Hunyuan3D Shape MLX y, si se solicita material, ejecuta Hunyuan3D Paint con
seis vistas. El flujo es local después de instalar dependencias y descargar
los pesos. No existe un generador Texto → multi-vista dentro del servidor
Python y no se crean placeholders cuando un modelo falla.

| Etapa | Implementación | Gate |
|---|---|---|
| Preparación | aislamiento opcional, encuadre y padding compatible | diagnóstico previo |
| Shape | `ShapePipeline.from_pretrained()` nativo MLX | caras, vértices, componentes y winding |
| Optimización | limpieza y decimación al perfil XR | validación posterior a decimación |
| Paint | Hunyuan3D Paint MLX, 6 vistas, 1K o 2K | PBR estructural + frente + cuartos |
| Entrega | GLB embebido; STL bajo demanda | exportación bloqueada en calidad crítica |
| Buffalo Strategic | contrato de piezas, regiones y preservación | candidato reducido o entrega maestra |

## Rendimiento Mac

- Shape y Paint se ejecutan secuencialmente para no solapar sus pesos en la
  memoria unificada.
- La carga fría de Shape se solapa únicamente con la preparación CPU de la
  referencia.
- El modelo Shape se libera y se limpia el caché MLX antes de Paint.
- El gate visual rasteriza a un máximo de 512 px y paraleliza sus tres vistas.
- El modelo Shape permanece caliente entre trabajos sin textura.
- El servidor limita los pools CPU y el caché MLX según el hardware detectado.
- La reducción de polígonos es transaccional: si pierde un componente
  significativo, se descarta y se conserva la geometría maestra.

No se publican porcentajes de aceleración sin un benchmark del mismo corpus,
perfil y equipo. El reporte de cada job incluye tiempo, geometría, gate de
textura y métricas de memoria MLX disponibles.

## Instalación reproducible

```bash
cd engine
./setup.sh
```

El instalador usa `requirements-macos.lock` y el commit fijado
`58e61ee5a86aec095387d9fcda343c1cab4aaa9e` de la adaptación MLX. Los pesos se
descargan en la primera conversión.

## API local

El proceso Electron levanta el servidor en `127.0.0.1:8765` con un token local
persistido y enviado por IPC. Endpoints activos:

- `GET /health`
- `POST /analyze`
- `POST /generate`
- `GET /status/{job_id}`
- `POST /cancel/{job_id}`
- `POST /to-stl`

## Licencia

La aplicación incluye Hunyuan3D-2.1 bajo el Tencent Hunyuan 3D 2.1 Community
License Agreement. El DMG instala la licencia y el Notice completos bajo
`Contents/Resources/legal/`. Revisa sus restricciones territoriales y de
redistribución antes de distribuir el ejecutable; esto requiere revisión legal.
