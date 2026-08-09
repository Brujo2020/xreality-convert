export const MODEL_CATEGORIES = {
  animal: {
    icon: '◉', label: 'Animal', description: 'Mascotas y cuadrúpedos con silueta completa.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 70000, guidance: 7.2,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.2, scale: 1,
  },
  person: {
    icon: '♙', label: 'Persona', description: 'Cuerpo entero, pose neutra y extremidades separadas.',
    profile: 'pcvr', steps: 40, octree: 192, targetFaces: 90000, guidance: 7.0,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.22, scale: 1.75,
  },
  product: {
    icon: '▧', label: 'Producto', description: 'Objetos comerciales con contorno y materiales limpios.',
    profile: 'mobile', steps: 25, octree: 128, targetFaces: 30000, guidance: 6.5,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.14, scale: 0.35,
  },
  industrial: {
    icon: '⌬', label: 'Industrial', description: 'Equipos y piezas con bordes y volumen técnico.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 70000, guidance: 6.5,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.14, scale: 1.5,
  },
  construction: {
    icon: '▤', label: 'Construcción', description: 'Estructuras, obra y maquinaria con piezas preservadas.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 90000, guidance: 6.2,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'keep', padding: 0.1, scale: 5,
  },
  warehouse: {
    icon: '▥', label: 'Bodega', description: 'Galpones y espacios industriales; multivista recomendada.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 100000, guidance: 5.5,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'keep', padding: 0.08, scale: 12,
  },
  vehicle: {
    icon: '◫', label: 'Vehículo liviano', description: 'Autos, SUV y utilitarios con ruedas, cristales y carrocería preservados.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 80000, guidance: 6.6,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.14, scale: 4.5,
  },
  cargo_vehicle: {
    icon: '▰', label: 'Vehículo de carga', description: 'Furgones, pickups y equipos de reparto con cabina y zona de carga separadas.',
    profile: 'xreal', steps: 36, octree: 192, targetFaces: 90000, guidance: 6.4,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.12, scale: 7,
  },
  truck: {
    icon: '▣', label: 'Camión', description: 'Camiones rígidos o tractocamiones; conserva ejes, ruedas, cabina y remolque.',
    profile: 'xreal', steps: 38, octree: 192, targetFaces: 100000, guidance: 6.4,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.12, scale: 11,
  },
  crane: {
    icon: '⌁', label: 'Grúa', description: 'Ensamblajes, pluma, cable y estabilizadores sin borrar piezas.',
    profile: 'xreal', steps: 38, octree: 192, targetFaces: 110000, guidance: 6.4,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.12, scale: 10,
  },
  electrical: {
    icon: 'ϟ', label: 'Instalación eléctrica', description: 'Tableros, aisladores, canalizaciones, transformadores y cableado visible.',
    profile: 'xreal', steps: 32, octree: 192, targetFaces: 70000, guidance: 6.0,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'keep', padding: 0.1, scale: 3,
  },
  vegetation: {
    icon: '♣', label: 'Vegetación', description: 'Árboles, arbustos y plantas con tronco, ramas y follaje diferenciados.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 80000, guidance: 6.8,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.18, scale: 4,
  },
  building: {
    icon: '▥', label: 'Edificio', description: 'Edificios completos con fachadas, cubiertas, ventanas y accesos preservados.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 110000, guidance: 5.6,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'keep', padding: 0.08, scale: 18,
  },
  tool: {
    icon: '⌕', label: 'Herramienta', description: 'Herramientas manuales y eléctricas con mango, accionamiento y piezas funcionales.',
    profile: 'xreal', steps: 30, octree: 192, targetFaces: 60000, guidance: 6.5,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.15, scale: 0.6,
  },
  forklift: {
    icon: '▦', label: 'Montacargas', description: 'Grúas horquilla con mástil, uñas, cabina, ruedas y contrapeso preservados.',
    profile: 'xreal', steps: 34, octree: 192, targetFaces: 80000, guidance: 6.3,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.13, scale: 2.5,
  },
  excavator: {
    icon: '◩', label: 'Excavadora', description: 'Maquinaria de movimiento de tierra con pluma, brazo, cucharón y orugas separados.',
    profile: 'xreal', steps: 38, octree: 192, targetFaces: 110000, guidance: 6.4,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.12, scale: 9,
  },
  motorcycle: {
    icon: '◒', label: 'Motocicleta', description: 'Motocicletas y scooters con dos ruedas, horquilla, motor y manillar completos.',
    profile: 'xreal', steps: 34, octree: 192, targetFaces: 70000, guidance: 6.7,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.16, scale: 2.2,
  },
  bus: {
    icon: '▭', label: 'Autobús', description: 'Buses urbanos, interurbanos y minibuses con ejes, puertas y ventanas preservados.',
    profile: 'xreal', steps: 38, octree: 192, targetFaces: 100000, guidance: 6.2,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.1, scale: 12,
  },
  drone: {
    icon: '⌘', label: 'Drone', description: 'Drones multirrotor con brazos, hélices, cámara, tren y cuerpo central.',
    profile: 'xreal', steps: 30, octree: 192, targetFaces: 55000, guidance: 6.8,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.18, scale: 0.8,
  },
  boat: {
    icon: '⌇', label: 'Embarcación', description: 'Lanchas y embarcaciones con casco, cubierta, cabina y propulsión legibles.',
    profile: 'xreal', steps: 36, octree: 192, targetFaces: 90000, guidance: 6.2,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.12, scale: 8,
  },
  furniture: {
    icon: '▱', label: 'Mobiliario', description: 'Sillas, mesas, estanterías y muebles con patas, uniones y materiales diferenciados.',
    profile: 'xreal', steps: 30, octree: 192, targetFaces: 55000, guidance: 6.1,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.16, scale: 1.2,
  },
  solar: {
    icon: '☼', label: 'Energía solar', description: 'Paneles, inversores, soportes y conjuntos fotovoltaicos como ensamblaje técnico.',
    profile: 'xreal', steps: 32, octree: 192, targetFaces: 80000, guidance: 5.9,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'keep', padding: 0.1, scale: 6,
  },
  architecture: {
    icon: '▥', label: 'Arquitectura', description: 'Mobiliario, salas y estructuras de gran escala.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 100000, guidance: 5.5,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'keep', padding: 0.08, scale: 8,
  },
  custom: {
    icon: '◇', label: 'Otro', description: 'Configuración neutral para un sujeto no clasificado.',
    profile: 'xreal', steps: 35, octree: 192, targetFaces: 70000, guidance: 6.0,
    textureSize: '1K', paintBackend: 'fast', backgroundMode: 'auto', padding: 0.16, scale: 1,
  },
};
