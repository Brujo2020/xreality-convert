# Shape multi-vista: instalación y promoción

La versión MLX de Shape incluida en la aplicación procesa una sola imagen. No
debe recibir un diccionario de cámaras ni declarar que empleó imágenes que no
consumió. La ruta multi-vista es un candidato aislado basado en el checkpoint
oficial `tencent/Hunyuan3D-2mv`, que admite las cámaras horizontales `front`,
`right`, `back` y `left`.

`top` y `bottom` se almacenan y se validan como evidencia adicional para QA;
no se inyectan al modelo 2mv porque éste no fue publicado para esas cámaras.
Esto evita distorsionar la semántica de cámara del checkpoint.

## Instalación explícita

Acepta primero la licencia del modelo en Hugging Face y autentica el CLI.
Después, con al menos 20 GiB libres:

```zsh
cd engine
./install_hunyuan2mv.sh
export XREALITY_MULTIVIEW_WEIGHTS_DIR="$PWD/models/Hunyuan3D-2mv"
export XREALITY_MULTIVIEW_SHAPE_WORKER=1
```

El worker requiere además la fuente oficial en
`engine/Hunyuan3D-2-official`, separada del port MLX 2.1. No se deben mezclar
sus paquetes (`hy3dgen` y `hy3dshape`).

El instalador no se llama desde la aplicación ni durante una generación. El
worker se ejecuta sin red (`HF_HUB_OFFLINE=1` y `TRANSFORMERS_OFFLINE=1`).

## Condiciones de habilitación

No habilitar para usuarios finales hasta superar en un Mac real:

1. Cuatro fotos reales, bien etiquetadas y con sujeto completo; seis para el
   flujo de revisión y perfiles MASTER.
2. Worker aislado que produzca un GLB válido y conserve en su informe qué
   cámaras consumió.
3. Gate de geometría, inventario semántico y renders canónicos; en animales se
   revisan ojos, patas, orejas y cola de manera explícita.
4. Pintura PBR y revisión humana. Ninguna vista sintética o región oculta se
   promociona como medida.

La ruta sigue siendo experimental hasta que registre paridad, memoria y
resultados de corpus frente al Shape MLX de una vista.
