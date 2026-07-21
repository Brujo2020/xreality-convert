import { MODEL_CATEGORIES } from './modelCategories.js';
import { XR_PROFILES } from './xrProfiles.js';

export function applyLowPolySkill(asset = {}) {
  return {
    ...asset,
    profile: 'lowpoly',
    octree: XR_PROFILES.lowpoly.octree,
    targetFaces: XR_PROFILES.lowpoly.targetFaces,
    textureSize: asset.texture ? '1K' : asset.textureSize || 'Sin textura',
  };
}

export function restoreCategoryDelivery(categoryId, asset = {}) {
  const category = MODEL_CATEGORIES[categoryId] || MODEL_CATEGORIES.custom;
  const profile = XR_PROFILES[category.profile] || XR_PROFILES.xreal;
  return {
    ...asset,
    profile: category.profile,
    octree: category.octree,
    targetFaces: category.targetFaces,
    texture: asset.texture,
    textureSize: asset.texture ? profile.textureSize : 'Sin textura',
  };
}
