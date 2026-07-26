# Tasks — Xreality TruthLoop 3D

Status: Proposed | Design: [design.md](design.md)

## W0 — Benchmark foundation

- [ ] 1. Define golden-set manifest, categories and licenses.
  - _Depends:_ none
  - _Boundary:_ datasets/tests only
- [ ] 2. Add deterministic GLB turntable renderer.
  - _Depends:_ 1
  - _Boundary:_ evaluator
- [ ] 3. Add silhouette, keypoint, identity, seam and PBR metrics.
  - _Depends:_ 2
  - _Boundary:_ evaluator
- [ ] 4. Capture current Hunyuan baseline and failure taxonomy.
  - _Depends:_ 1–3
  - _Gate:_ 60 assets with reproducible reports

## W1 — AssetGraph and TruthLoop

- [ ] 5. Define versioned `AssetGraph` schema and migration.
  - _Depends:_ 4
  - _Boundary:_ shared contract
- [ ] 6. Persist directed source views and observed/generated provenance.
  - _Depends:_ 5
- [ ] 7. Emit per-view coverage, uncertainty and heatmaps.
  - _Depends:_ 3, 6
- [ ] 8. Integrate read-only TruthLoop report into the viewer.
  - _Depends:_ 7
  - _Gate:_ same artifact produces identical scores

## W2 — Texture truth

- [ ] 9. Implement source de-lighting with before/after preview.
  - _Depends:_ 6
- [ ] 10. Add material segmentation and category-aware PBR estimation.
  - _Depends:_ 5, 9
- [ ] 11. Replace uniform bake with visibility/occlusion/confidence weights.
  - _Depends:_ 7, 10
- [ ] 12. Export confidence atlas and seam heatmap.
  - _Depends:_ 11
- [ ] 13. Add identity locks for eyes, face, logos, text and colors.
  - _Depends:_ 5, 11
  - _Gate:_ visible texture failures reduced ≥50% vs W0

## W3 — Corrective editing

- [ ] 14. Add 3D brush mask and region selection.
  - _Depends:_ 8
- [ ] 15. Implement transactional regional texture repair.
  - _Depends:_ 12–14
- [ ] 16. Add version comparison, undo and redo.
  - _Depends:_ 15
  - _Gate:_ unselected regions change <1%

## W4 — Parts and topology

- [ ] 17. Implement semantic part adapter and stable IDs.
  - _Depends:_ 5
- [ ] 18. Add hierarchy, locks, names and per-part materials.
  - _Depends:_ 17
- [ ] 19. Derive hero/game/print meshes with correspondence maps.
  - _Depends:_ 18
- [ ] 20. Add per-part local geometry edit transaction.
  - _Depends:_ 18–19
  - _Gate:_ transforms, materials and locks survive round-trip

## W5 — Council and delivery

- [ ] 21. Define backend capability manifest and adapter test suite.
  - _Depends:_ 4–5
- [ ] 22. Implement routing policy by category, hardware and benchmark.
  - _Depends:_ 21
- [ ] 23. Add adaptive effort and early exit from quality gates.
  - _Depends:_ 8, 22
- [ ] 24. Add category expert policies and tests.
  - _Depends:_ 10, 17, 22
- [ ] 25. Compile target profiles, LOD, collider and formats.
  - _Depends:_ 19, 24
- [ ] 26. Generate Evidence Pack and runtime validator results.
  - _Depends:_ 25
  - _Gate:_ Blender, Three.js and selected target pass

## W6 — Rigging and competitive proof

- [ ] 27. Add prer rig check and part-aware skeleton adapter.
  - _Depends:_ 18–19
- [ ] 28. Validate skin weights with deformation tests.
  - _Depends:_ 27
- [ ] 29. Run blind comparison against Rodin, Tripo and Meshy.
  - _Depends:_ 26
- [ ] 30. Publish inputs, outputs, parameters and orbital renders.
  - _Depends:_ 29
  - _Gate:_ win ≥4/6 primary metrics without cherry-picking

## Critical path

`1 → 2 → 3 → 4 → 5 → 6 → 7 → 11 → 12 → 15 → 16`

This path fixes the current visual texture failure before model routing, rigging
or broad production expansion.
