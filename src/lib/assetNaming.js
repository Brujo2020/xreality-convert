const DEFAULT_PREFIX = 'xreality-asset';

export function sanitizeAssetName(value, fallback = DEFAULT_PREFIX) {
  const normalized = String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 72);
  return normalized || fallback;
}

export function buildAssetName({ sourceName, prompt, category, profile, createdAt = Date.now() } = {}) {
  const date = new Date(createdAt);
  const stamp = [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('');
  const sourceBase = String(sourceName || prompt || DEFAULT_PREFIX).replace(/\.[^.]+$/, '');
  const parts = [
    sanitizeAssetName(sourceBase),
    sanitizeAssetName(category || 'custom'),
    sanitizeAssetName(profile || 'xreal'),
    stamp,
  ];
  return parts.filter(Boolean).join('-');
}

export function assetFilename(assetName, ext) {
  const cleanExt = String(ext || '').replace(/^\./, '').toLowerCase();
  return `${sanitizeAssetName(assetName)}.${cleanExt || 'asset'}`;
}
