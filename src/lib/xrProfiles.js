export const XR_PROFILES = {
  lowpoly: {
    label: 'Low Poly PBR', icon: '◇', description: '15K, PBR 1K y malla maestra preservada',
    octree: 128, steps: 24, texture: true, targetFaces: 15000, textureSize: '1K', paintBackend: 'fast', materialHint: 'auto', scale: 1,
  },
  mobile: {
    label: 'Móvil AR', icon: '◌', description: 'WebAR, redes y dispositivos móviles',
    octree: 128, steps: 25, texture: true, targetFaces: 20000, textureSize: '1K', paintBackend: 'fast', materialHint: 'auto', scale: 1,
  },
  quest: {
    label: 'Meta Quest', icon: '◉', description: 'VR autónoma con rendimiento estable',
    octree: 192, steps: 30, texture: true, targetFaces: 50000, textureSize: '2K', paintBackend: 'fast', materialHint: 'auto', scale: 1,
  },
  vrready: {
    label: 'VR Ready', icon: '◎', description: '45K y PBR 1K para VR fluida y portable',
    octree: 192, steps: 32, texture: true, targetFaces: 45000, textureSize: '1K', paintBackend: 'fast', materialHint: 'auto', scale: 1,
  },
  smart: {
    label: 'Smart Apple M', icon: '✺', description: 'Ajuste automático por memoria unificada sin duplicar inferencia',
    octree: 192, steps: 32, texture: true, targetFaces: 60000, textureSize: '1K', paintBackend: 'fast', materialHint: 'auto', scale: 1,
  },
  xreal: {
    label: 'Xreality Industrial', icon: '✦', description: 'Gemelos digitales, asistencia espacial y operaciones en terreno',
    octree: 192, steps: 35, texture: true, targetFaces: 50000, textureSize: '2K', paintBackend: 'fast', materialHint: 'auto', scale: 1,
  },
  pcvr: {
    label: 'PC VR', icon: '▣', description: 'SteamVR, Vive y escenas de alta fidelidad',
    octree: 256, steps: 40, texture: true, targetFaces: 100000, textureSize: '2K', paintBackend: 'fast', materialHint: 'auto', scale: 1,
  },
  maxquality: {
    label: 'Máxima calidad', icon: '◆', description: 'Shape maestro + Agentic 1K verificado; mapas premium son fail-closed',
    octree: 256, steps: 50, texture: true, targetFaces: 200000, textureSize: '1K', paintBackend: 'agentic', materialHint: 'auto', scale: 1,
  },
};

export function profileAudit(profile, faces) {
  if (!faces) return { level: 'pendiente', text: 'Genera un modelo para auditarlo.' };
  if (faces <= profile.targetFaces) return { level: 'listo', text: 'Dentro del presupuesto Xreality.' };
  if (faces <= profile.targetFaces * 1.35) return { level: 'atencion', text: 'Funciona, pero conviene optimizar.' };
  return { level: 'critico', text: 'Excede el presupuesto; usa un preset más ligero.' };
}
