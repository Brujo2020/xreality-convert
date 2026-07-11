export const MODEL_CATEGORIES = {
  animal: {
    icon: '◉', label: 'Animal', description: 'Mascotas y cuadrúpedos con silueta completa.',
    profile: 'xreal', steps: 50, octree: 256, targetFaces: 100000, guidance: 7.5,
    backgroundMode: 'auto', padding: 0.2, scale: 1,
  },
  person: {
    icon: '♙', label: 'Persona', description: 'Cuerpo entero, pose neutra y extremidades separadas.',
    profile: 'pcvr', steps: 50, octree: 256, targetFaces: 120000, guidance: 7.0,
    backgroundMode: 'auto', padding: 0.22, scale: 1.75,
  },
  product: {
    icon: '▧', label: 'Producto', description: 'Objetos comerciales con contorno y materiales limpios.',
    profile: 'mobile', steps: 40, octree: 256, targetFaces: 80000, guidance: 6.5,
    backgroundMode: 'auto', padding: 0.14, scale: 0.35,
  },
  industrial: {
    icon: '⌬', label: 'Industrial', description: 'Equipos y piezas con bordes y volumen técnico.',
    profile: 'xreal', steps: 45, octree: 256, targetFaces: 100000, guidance: 6.5,
    backgroundMode: 'auto', padding: 0.14, scale: 1.5,
  },
  architecture: {
    icon: '▥', label: 'Arquitectura', description: 'Mobiliario, salas y estructuras de gran escala.',
    profile: 'pcvr', steps: 45, octree: 256, targetFaces: 150000, guidance: 5.5,
    backgroundMode: 'keep', padding: 0.08, scale: 5,
  },
  custom: {
    icon: '◇', label: 'Otro', description: 'Configuración neutral para un sujeto no clasificado.',
    profile: 'xreal', steps: 40, octree: 256, targetFaces: 100000, guidance: 6.0,
    backgroundMode: 'auto', padding: 0.16, scale: 1,
  },
};
