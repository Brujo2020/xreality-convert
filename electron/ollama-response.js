function extractGeneratedText(data) {
  if (!data || typeof data !== 'object') return '';
  const candidates = [data.response, data.message?.content];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate;
  }

  // Some reasoning models place the complete code in `thinking` when they hit
  // their output boundary before producing a final response.
  if (typeof data.thinking === 'string' && /module\.exports|function\s+main|```(?:js|javascript|jscad)/i.test(data.thinking)) {
    return data.thinking;
  }
  return '';
}

module.exports = { extractGeneratedText };
