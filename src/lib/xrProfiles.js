export const XR_PROFILES = {
  lowpoly: {
    label: 'Low Poly', icon: '◇', description: 'Props ligeros y estilo estilizado',
    octree: 128, steps: 20, texture: false, targetFaces: 12000, textureSize: 'Sin textura', scale: 1,
  },
  mobile: {
    label: 'Móvil AR', icon: '◌', description: 'WebAR, redes y dispositivos móviles',
    octree: 128, steps: 25, texture: true, targetFaces: 20000, textureSize: '1K', scale: 1,
  },
  quest: {
    label: 'Meta Quest', icon: '◉', description: 'VR autónoma con rendimiento estable',
    octree: 192, steps: 30, texture: true, targetFaces: 50000, textureSize: '2K', scale: 1,
  },
  xreal: {
    label: 'Xreality Industrial', icon: '✦', description: 'Gemelos digitales, asistencia espacial y operaciones en terreno',
    octree: 192, steps: 35, texture: true, targetFaces: 50000, textureSize: '2K', scale: 1,
  },
  pcvr: {
    label: 'PC VR', icon: '▣', description: 'SteamVR, Vive y escenas de alta fidelidad',
    octree: 256, steps: 40, texture: true, targetFaces: 100000, textureSize: '2K', scale: 1,
  },
  maxquality: {
    label: 'Máxima calidad', icon: '◆', description: 'Máximo detalle local para activo maestro',
    octree: 256, steps: 50, texture: true, targetFaces: 200000, textureSize: '2K', scale: 1,
  },
};

export function profileAudit(profile, faces) {
  if (!faces) return { level: 'pendiente', text: 'Genera un modelo para auditarlo.' };
  if (faces <= profile.targetFaces) return { level: 'listo', text: 'Dentro del presupuesto Xreality.' };
  if (faces <= profile.targetFaces * 1.35) return { level: 'atencion', text: 'Funciona, pero conviene optimizar.' };
  return { level: 'critico', text: 'Excede el presupuesto; usa un preset más ligero.' };
}
