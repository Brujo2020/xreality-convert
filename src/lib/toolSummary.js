export function summarizeTools(tools) {
  return (Array.isArray(tools) ? tools : []).reduce(
    (summary, tool) => {
      summary.total += 1;
      if (tool?.status === 'ready') {
        summary.ready += 1;
        if (tool.bundled === true) summary.bundledReady += 1;
      } else if (tool?.status === 'missing') {
        summary.missing += 1;
      } else {
        summary.blocked += 1;
      }
      return summary;
    },
    { ready: 0, bundledReady: 0, missing: 0, blocked: 0, total: 0 }
  );
}
