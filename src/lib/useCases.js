export const USE_CASES = {
  industrial: {
    icon: '⌬', label: 'Activo industrial', tag: 'Digital twin',
    description: 'Máquinas, herramientas, componentes y equipos de planta.',
    mode: 'image3d', category: 'industrial', profile: 'xreal', scale: 1.5, stlMm: 150,
    prompt: 'equipo industrial aislado, vista tres cuartos, geometría completa, iluminación uniforme, fondo blanco puro, sin personas ni texto',
    route: ['Referencia limpia', 'Malla 50K', 'GLB XR'],
  },
  product: {
    icon: '▧', label: 'Producto comercial', tag: 'Catálogo 3D',
    description: 'Productos, packaging y objetos para web o comercio espacial.',
    mode: 'image', category: 'product', profile: 'mobile', scale: 0.35, stlMm: 100,
    prompt: 'fotografía de producto de un objeto completo, centrado, vista tres cuartos, iluminación de estudio suave, fondo blanco puro, sin sombras duras, sin texto',
    route: ['Crear imagen', 'Malla 20K', 'Móvil AR'],
  },
  organic: {
    icon: '◉', label: 'Animal o personaje', tag: 'Forma orgánica',
    description: 'Animales, mascotas, figuras y sujetos con anatomía orgánica.',
    mode: 'image', category: 'animal', profile: 'pcvr', scale: 1, stlMm: 120,
    prompt: 'sujeto de cuerpo entero, pose neutra de pie, vista tres cuartos, anatomía clara, objeto centrado, iluminación uniforme, fondo blanco puro, sin accesorios ni personas adicionales',
    route: ['Crear referencia', 'Hunyuan MLX', 'GLB 100K'],
  },
  mobilexr: {
    icon: '◌', label: 'Móvil y WebXR', tag: 'Rendimiento',
    description: 'Activos ligeros para navegador, tablet y realidad aumentada móvil.',
    mode: 'image3d', category: 'product', profile: 'mobile', scale: 1, stlMm: 100,
    prompt: 'objeto simple y completo, silueta limpia, pocos detalles pequeños, fondo blanco puro',
    route: ['Referencia', 'Malla 20K', 'Textura 1K'],
  },
  print3d: {
    icon: '△', label: 'Impresión 3D', tag: 'STL sólido',
    description: 'Piezas paramétricas, soportes y prototipos imprimibles.',
    mode: 'stl', category: 'industrial', profile: 'lowpoly', scale: 0.12, stlMm: 120,
    prompt: 'pieza funcional imprimible, sólida y watertight, base plana, paredes de mínimo 2 mm, dimensiones aproximadas 120 mm',
    route: ['Texto técnico', 'Sólido watertight', 'STL'],
  },
  master: {
    icon: '◆', label: 'Activo maestro', tag: 'Máxima calidad',
    description: 'Modelo base de alta fidelidad para optimizar después en distintas salidas.',
    mode: 'image3d', category: 'custom', profile: 'maxquality', scale: 1, stlMm: 150,
    prompt: 'objeto completo de alta fidelidad, detalles visibles, iluminación de estudio uniforme, vista tres cuartos, fondo blanco puro',
    route: ['Referencia 2K', 'Malla 200K', 'GLB maestro'],
  },
};
