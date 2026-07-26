export const CANONICAL_RENDER_PROFILE = Object.freeze({
  version: 'xreality-canonical-v1',
  width: 1024,
  height: 1024,
  fovDegrees: 35,
  elevationDegrees: 15,
  background: 0x737373,
  margin: 1.08,
});

export const CANONICAL_ORBIT_VIEWS = Object.freeze(
  Array.from({ length: 8 }, (_, index) => Object.freeze({
    viewId: `orbit-${String(index).padStart(2, '0')}`,
    azimuthDegrees: index * 45,
    elevationDegrees: CANONICAL_RENDER_PROFILE.elevationDegrees,
  })),
);

export function cameraPositionForView(view, distance) {
  const azimuth = view.azimuthDegrees * Math.PI / 180;
  const elevation = view.elevationDegrees * Math.PI / 180;
  const horizontal = Math.cos(elevation) * distance;
  return {
    x: Math.sin(azimuth) * horizontal,
    y: Math.sin(elevation) * distance,
    z: Math.cos(azimuth) * horizontal,
  };
}

export function cameraDistanceForRadius(radius, profile = CANONICAL_RENDER_PROFILE) {
  const halfFov = profile.fovDegrees * Math.PI / 360;
  return (Math.max(radius, Number.EPSILON) * profile.margin) / Math.sin(halfFov);
}
