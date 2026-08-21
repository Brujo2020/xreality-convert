# Delivery, arena and cloud

- Validate every primitive/material, embedded URI, texture bytes and extension
  with glTF Validator plus Blender/target-runtime round-trip.
- Derive target-specific LOD, compression and textures from the master; rebake
  and gate each variant. Verify pivot, units, ground contact, collision and
  animation where required.
- For web, set measurable triangles, draw calls, texture memory and load-time
  budgets; choose Meshopt/Draco and KTX2 only after runtime tests. Provide a
  non-3D/accessibility fallback.
- For USDZ, normalize the package and require `usdchecker --arkit --strict`.
- Benchmark challengers on a sealed corpus with pinned revisions, sequential
  seeds, p50/p95 time, peak/swap, artefacts, cost and blind visual review.
- Keep provider states `champion`, `challenger`, `research-only`, `quarantined`
  or `retired`; claims and screenshots are not evidence.
- Cloud sequence: `estimate -> consent -> submit -> poll -> download -> verify
  -> reconcile`. Disable auto-refill, cap retries, isolate credentials and
  retain provider/model/license/provenance.
- Prefer transparent pay-as-you-go for rare calls; subscriptions are justified
  only by measured volume. Recheck official pricing immediately before spend.
