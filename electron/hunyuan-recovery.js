const path = require('node:path');

function recovered3DFromReport(report, engineDir, exists) {
  const jobId = String(report?.job_id || '');
  if (!/^[a-f0-9]{32}$/.test(jobId)) return null;
  const glbPath = path.join(engineDir, 'jobs', `${jobId}.glb`);
  if (!exists(glbPath)) return null;

  const input = report.input || {};
  const metrics = report.metrics || {};
  const texture = report.texture || {};
  const shapeGlbPath = texture.shape_glb_path;
  const referencePath = path.join(engineDir, 'jobs', `${jobId}.png`);
  return {
    jobId,
    glbPath,
    lodPaths: report.lods || {},
    faces: metrics.faces,
    duration: report.elapsed,
    reportPath: path.join(engineDir, 'jobs', 'reports', `${jobId}.json`),
    qualityLevel: metrics.level,
    qualityScore: metrics.score,
    qualityText: Array.isArray(metrics.reasons) ? metrics.reasons.join(' ') : '',
    lowpolyRefinement: metrics.lowpoly_refinement || null,
    textureApplied: !!texture.applied,
    textureRequested: !!texture.requested,
    textureSize: texture.profile || null,
    textureReport: texture.gate || null,
    shapeGlbPath: shapeGlbPath && exists(shapeGlbPath) ? shapeGlbPath : null,
    referencePath: exists(referencePath) ? referencePath : null,
    profile: input.profile || 'xreal',
    category: input.category || 'custom',
    steps: input.steps,
    targetFaces: input.target_faces,
    scale: input.scale_meters,
    guidance: input.guidance,
    backgroundMode: input.background_mode,
    pivot: input.pivot || 'center',
    pivotCustom: input.pivot_custom || null,
    upAxis: input.up_axis || 'y',
    units: input.units || 'm',
    createdAt: Math.round(Number(report.created_at || 0) * 1000),
  };
}

module.exports = { recovered3DFromReport };
