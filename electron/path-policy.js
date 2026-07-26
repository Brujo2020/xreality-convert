const path = require('node:path');

function resolveWithinRoots(candidate, roots) {
  if (typeof candidate !== 'string' || !candidate.trim()) return null;
  const resolved = path.resolve(candidate);
  const allowed = roots.some((root) => {
    const resolvedRoot = path.resolve(root);
    return resolved === resolvedRoot || resolved.startsWith(`${resolvedRoot}${path.sep}`);
  });
  return allowed ? resolved : null;
}

function safeOutputFilename(candidate, allowedExtensions) {
  if (typeof candidate !== 'string') return null;
  const trimmed = candidate.trim();
  const filename = path.basename(trimmed);
  if (filename !== trimmed) return null;
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(filename)) return null;
  const extension = path.extname(filename).toLowerCase();
  return allowedExtensions.includes(extension) ? filename : null;
}

module.exports = { resolveWithinRoots, safeOutputFilename };
