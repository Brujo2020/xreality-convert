const CATEGORY_PROMPT_HINTS = {
  animal: 'full body animal, clear silhouette, visible legs, tail and ears, isolated subject, simple background',
  person: 'full body person, neutral pose, separated arms and legs, complete feet and hands, simple background',
  product: 'single product, clean contour, centered object, visible base, sharp edges, studio background',
  industrial: 'industrial asset, technical volume, clear components, hard edges, centered, simple background',
  architecture: 'architectural scene, complete structure, visible floor and walls, coherent scale, wide view',
  custom: 'single complete subject, centered, unobstructed, clear silhouette, reconstruction-friendly view',
};

export function enrichImagePrompt(prompt, category) {
  const base = prompt.trim();
  const hint = CATEGORY_PROMPT_HINTS[category] || CATEGORY_PROMPT_HINTS.custom;
  return `${base}. ${hint}.`;
}
