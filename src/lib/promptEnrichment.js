const CATEGORY_PROMPT_HINTS = {
  animal: 'photorealistic full body animal, natural fur colors and texture, visible legs, tail and ears, isolated subject, plain white background',
  person: 'photorealistic full body person, neutral pose, separated arms and legs, complete feet and hands, plain white background',
  product: 'photorealistic single product, clean contour, centered object, visible base, sharp edges, studio lighting, plain white background',
  industrial: 'photorealistic industrial asset, physically plausible metal and polymer surfaces, clear components, hard edges, centered',
  architecture: 'photorealistic architectural space, complete structure, visible floor and walls, coherent scale, realistic construction materials',
  custom: 'photorealistic single complete subject, centered, unobstructed, realistic surface detail, reconstruction-friendly view',
};

const LIGHTING_HINTS = {
  studio: 'soft studio lighting with natural shadows',
  natural: 'natural daylight with realistic shadows',
  overcast: 'soft overcast daylight with even exposure',
  dramatic: 'controlled dramatic photography lighting with preserved surface detail',
};

const VIEW_HINTS = {
  front: 'front view at eye level',
  threeQuarter: 'three-quarter view at eye level',
  side: 'clean side view at eye level',
  orthographic: 'orthographic product photography view with minimal perspective distortion',
};

const BACKGROUND_HINTS = {
  plain: 'plain neutral background with no props',
  white: 'seamless white studio background with no props',
  transparent: 'isolated subject on a uniform chroma-free background',
  contextual: 'realistic but uncluttered real-world context',
};

export function enrichImagePrompt(prompt, category, options = {}) {
  const base = prompt.trim();
  const hint = CATEGORY_PROMPT_HINTS[category] || CATEGORY_PROMPT_HINTS.custom;
  const lighting = LIGHTING_HINTS[options.lighting] || LIGHTING_HINTS.studio;
  const view = VIEW_HINTS[options.view] || VIEW_HINTS.threeQuarter;
  const background = BACKGROUND_HINTS[options.background] || BACKGROUND_HINTS.plain;
  const custom = String(options.customInstructions || '').trim();
  return [
    base,
    hint,
    lighting,
    view,
    background,
    'real-world photography only, physically plausible materials and surface micro-detail',
    'exclude illustration, drawing, sketch, painting, cartoon, concept art, blueprint and clay render styles',
    custom,
  ].filter(Boolean).map((part) => part.replace(/[.\s]+$/g, '')).join('. ') + '.';
}
