# Geometry and Blender

- Generate an accepted master before low-poly/LOD derivation.
- Measure finite vertices/normals, degenerates, winding, components, scale,
  silhouette, screen/Hausdorff error and category-specific part survival.
- Require watertightness for closed solids, not blindly for rooms/assemblies.
- Protect material borders, hard normals, UV seams and thin/critical parts.
- Treat every decimate/remesh/retopo as a candidate; compare fingerprints and
  discard it if structure drifts.
- Use Blender headless for scripted round-trip, inspection, repair, UV, bake
  and canonical renders. Version scripts and preserve the temporary `.blend`.
- Never apply global merge-by-distance, component deletion or remesh without a
  pre/post gate.
- Render unlit, front and quarters, grazing light, plus alpha/transmission
  checkers when relevant.
- Recycle the Blender subprocess and remove high-resolution temporary data at
  the phase boundary.

