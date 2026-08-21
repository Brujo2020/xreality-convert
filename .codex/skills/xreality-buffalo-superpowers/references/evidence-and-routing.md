# Evidence and routing

- Separate delivery intent, semantic category and material regions.
- Label every claim `measured`, `inferred`, `synthetic` or `not_measured`.
- Require real multiview for hidden geometry, assemblies and master candidates.
- Reject ambiguous silhouettes, occlusion of critical parts, destructive crop,
  unusable background separation and missing scale cues before inference.
- Build a parts inventory with min/max counts, criticality and thin-structure
  flags. Never use “largest component” as a semantic classifier.
- Route preview/mobile/XR/hifi/master independently from asset category.
- Define success as an explicit gate matrix before implementation; make the
  minimum surgical change that can move the failed lane.
- Record privacy, input license and whether web transfer is permitted.

