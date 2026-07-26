import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CANONICAL_ORBIT_VIEWS,
  CANONICAL_RENDER_PROFILE,
  cameraDistanceForRadius,
  cameraPositionForView,
} from './canonicalViews.js';

test('canonical orbit defines eight stable 45 degree views', () => {
  assert.equal(CANONICAL_ORBIT_VIEWS.length, 8);
  assert.deepEqual(
    CANONICAL_ORBIT_VIEWS.map((view) => view.azimuthDegrees),
    [0, 45, 90, 135, 180, 225, 270, 315],
  );
  assert.equal(new Set(CANONICAL_ORBIT_VIEWS.map((view) => view.viewId)).size, 8);
});

test('camera positions keep constant distance around the asset', () => {
  const distance = cameraDistanceForRadius(2);
  const positions = CANONICAL_ORBIT_VIEWS.map((view) => (
    cameraPositionForView(view, distance)
  ));

  positions.forEach(({ x, y, z }) => {
    assert.ok(Math.abs(Math.hypot(x, y, z) - distance) < 1e-9);
  });
  assert.ok(positions[0].z > 0);
  assert.ok(positions[2].x > 0);
  assert.equal(CANONICAL_RENDER_PROFILE.width, 1024);
  assert.equal(CANONICAL_RENDER_PROFILE.fovDegrees, 35);
});
