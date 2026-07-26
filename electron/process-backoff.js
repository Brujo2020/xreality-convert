function nextRestartDelayMs(attempt, { baseMs = 1000, maxMs = 30000 } = {}) {
  const normalizedAttempt = Math.max(1, Number.isFinite(attempt) ? attempt : 1);
  return Math.min(maxMs, baseMs * 2 ** (normalizedAttempt - 1));
}

function isTransientLocalPollError(error) {
  const code = String(error?.code || '').toUpperCase();
  const message = String(error?.message || error || '').toUpperCase();
  return ['ECONNRESET', 'ECONNREFUSED', 'EPIPE', 'ETIMEDOUT'].includes(code)
    || /TIMEOUT|SOCKET HANG UP/.test(message);
}

module.exports = { isTransientLocalPollError, nextRestartDelayMs };
