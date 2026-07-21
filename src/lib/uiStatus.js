export function getControlStatus(value, recommended, { min = -Infinity, max = Infinity, tolerance = 0 } = {}) {
  const numericValue = typeof value === 'number' ? value : Number(value);
  if (Number.isFinite(numericValue) && (numericValue < min || numericValue > max)) {
    return 'out';
  }
  if (value === recommended) return 'recommended';
  if (
    typeof value === 'number' &&
    typeof recommended === 'number' &&
    Math.abs(value - recommended) <= tolerance
  ) {
    return 'recommended';
  }
  return 'modified';
}

export function getAuditSemaphore(auditLevel) {
  if (auditLevel === 'listo' || auditLevel === 'Alta') return 'green';
  if (auditLevel === 'atencion' || auditLevel === 'Media') return 'amber';
  return 'red';
}
