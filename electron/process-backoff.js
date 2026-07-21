function nextRestartDelayMs(attempt, { baseMs = 1000, maxMs = 30000 } = {}) {
  const normalizedAttempt = Math.max(1, Number.isFinite(attempt) ? attempt : 1);
  return Math.min(maxMs, baseMs * 2 ** (normalizedAttempt - 1));
}

module.exports = { nextRestartDelayMs };
