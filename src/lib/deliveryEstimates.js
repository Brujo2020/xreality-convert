const PROFILE_BASE_MINUTES = {
  lowpoly: 5,
  mobile: 6,
  quest: 8,
  xreal: 9,
  pcvr: 12,
  maxquality: 16,
};

const PROFILE_MEMORY_GB = {
  lowpoly: 9,
  mobile: 10,
  quest: 12,
  xreal: 13,
  pcvr: 15,
  maxquality: 18,
};

export function estimateImage3dDelivery({ asset, analysis, textureEnabled }) {
  const profile = asset?.profile || 'xreal';
  const minutes = (PROFILE_BASE_MINUTES[profile] || PROFILE_BASE_MINUTES.xreal)
    + (textureEnabled ? 4 : 0)
    + (analysis?.status === 'Procesable con ajustes' ? 2 : 0);
  const memoryGb = (PROFILE_MEMORY_GB[profile] || PROFILE_MEMORY_GB.xreal)
    + (textureEnabled ? 4 : 0);
  const quality = analysis?.status === 'Óptima'
    ? 'Alta'
    : analysis?.status === 'No recomendada'
      ? 'Riesgo alto'
      : analysis?.status === 'Procesable con ajustes'
        ? 'Media'
        : 'Pendiente';
  return {
    quality,
    minutes,
    memoryGb,
    textureReady: Boolean(textureEnabled),
    lowPolyReady: profile === 'lowpoly',
  };
}
