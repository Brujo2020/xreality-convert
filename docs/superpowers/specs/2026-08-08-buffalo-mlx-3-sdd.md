# Buffalo MLX 3.0 - Secure Evidence-Driven 3D Compiler

**Status:** In progress - control-plane/security foundation implemented; model
and DCC rollout remains staged  
**Date:** 2026-08-08  
**Scope:** next architecture-improvement phase for Xreality Convert  
**Supersedes:** architecture intent in `BUFFALO_MLX_ARCHITECTURE.md` only where
this specification is more precise  
**Source paper:** Hunyuan3D-Buffalo 1.0, inspected from the local 33-page PDF  
**Implementation claim:** none; every unbuilt capability is marked `target` or
`research`

## Implementation record (2026-08-08)

Implemented in this repository:

- version-3 job contracts, content-addressed evidence manifests, append-only
  journal, atomic snapshots and stage result files;
- strict control-plane state transitions and non-self-certifying `NON_MASTER`
  completion state;
- bounded base64/image validation, original input preservation and read-only
  evidence sealing;
- stable semantic part/material IDs, evidence classes/localizer slots and a
  typed edit-delta contract that rejects target/protected overlap;
- fail-closed GLB container validation before STL/USDZ conversion and conversion
  restricted to managed job assets;
- local-only Agentic model resolution: missing weights block the job instead of
  downloading during inference;
- reusable isolated-stage supervisor now owns offline worker environment,
  timeout, pressure/swap watchdog and graceful terminate/kill escalation for
  Agentic Paint;
- an opt-in disposable Shape MLX worker now emits a validated GLB and report,
  then exits to release Python/Metal allocations before geometry and Paint;
  its parent validates the output/provider contract and records watchdog
  evidence in the immutable stage result;
- a reproducible resident-versus-worker parity gate compares finite geometry,
  vertices/faces, components, extents and latency with explicit thresholds;
  it never substitutes structural parity for visual review or corpus evidence;
- startup recovery now scans durable ledgers and appends a safe terminal
  transition for interrupted jobs; it never replays in-memory ML implicitly;
- an explicit retry endpoint creates a new, lineage-linked attempt only from a
  restart-recovered job's sealed request and original local image; it never
  reopens or mutates the source attempt;
- isolated canonical Blender validation is implemented as an offline,
  fail-closed evidence service; target runtime budget certification and the
  first executable typed edit (`replace_material`) are available locally,
  while viewer/device rendering remains explicitly not measured;
- semantic part/material graphs, hash-bound derivative lineage and a local
  adversarial GLB corpus are implemented; actual DCC derivation and target
  viewer runs remain staged rather than inferred from these contracts;
- transactional Blender repair/retopo/UV operations, sealed challenger shadow
  arena reports, and hash-bound named human-review records are implemented;
  model promotion remains manual and evidence-gated.
- local GLB LOD derivation is executable with a mandatory independent PBR
  rebake; regional PBR auditing and config-owned review policy loading are
  fail-closed. Device/viewer and artistic quality remain explicitly measured
  only by their future real evidence lanes.
- the only local route to `MASTER` is now a sealed policy + sealed reviewer
  registry + all hash-bound gate files + an explicit named-human decision;
  automatic jobs stop durably at `HUMAN_REVIEW_REQUIRED`, including across a
  control-process restart. The endpoint is disabled until an operator provides
  those sealed configuration files and still cannot turn missing gate evidence
  into a pass.
- promotion gate files now require a second provenance hop: an immutable,
  code-owned, lane-specific source attestation under the same job, bound to the
  reviewed asset. Generic `stage=passed` JSON, arbitrary HTTP booleans and
  mutable source files cannot be used as evidence.
- optional-cloud authority is now local and provider-API-free: the provider allow-list
  defaults to empty, consent is immutable and bound to one job-local artifact,
  provider, operation, expiry and integer micro-cost ceiling; reservation,
  reconciliation and an irreversible per-job kill switch are auditable. No
  provider adapter, credential handling or network upload is implemented.
- a sealed, deterministic offline acceptance-campaign evaluator now requires
  exactly 30 fixed cases and preserves `not_measured`/`inconclusive` rather
  than treating them as a pass. Its local repository now admits each sealed
  case exactly once and can finalize only the complete 30-case aggregate. It
  is still an evaluator/repository; the physical 30-job run is required.
- offline supply-chain manifests now pin local models, skills and scripts to a
  canonical HTTPS repository, full Git commit, allowlisted licence and actual
  artifact hashes. Separate runtime-probe evidence can bind genuine external
  web/XR/mobile/USDZ executions to frames and logs, but neither module starts a
  viewer, downloads a weight or claims a device measurement by itself.
- a map-level PBR quality gate now measures embedded base-color,
  metallic/roughness and normal texture payloads, UV bindings, bounded pixel
  variation and alpha/transmission declarations per semantic region. It
  rejects empty/constant/external/malformed maps while continuing to label
  reference alignment, relighting, baked-light absence and artistic quality as
  `not_measured` until render evidence exists.
- the 30-case local corpus now has a sealed preflight inventory that binds
  actual local bytes, source stratum, licence/consent and observed real-view
  count; master candidates reject synthetic/provider-only evidence and fewer
  than two real observed views. Geometry audit now records finite topology,
  degenerates, components, bounds, winding and required watertightness while
  openly retaining silhouette/thin-part/self-intersection as `not_measured`
  where no robust measurement exists.
- canonical-render evidence can now bind a real Blender output matrix
  (unlit, three neutral views, grazing, wireframe, semantic-part and applicable
  alpha/transmission checks) to the exact GLB and semantic graph. It does not
  render or self-certify; an actual Blender run remains required.
- an independent glTF Validator lane is exposed through the local control
  plane. It invokes only a locally installed `gltf-validator` CLI in an
  offline worker and reports its absence as `not_measured`; it never substitutes
  a parser or Blender import for Khronos validation.
- control-plane paths/state exposed through the job status API;
- unit coverage for journal, contracts, safe GLB handling, semantic delta and
  offline model resolution.

Still staged/target: promotion of the opt-in Shape worker to the default path
(it must first pass a real-Metal parity/latency trial; the expensive local E2E
probe is explicitly gated), persisted resume
runner, production Blender sandbox/canonical-render trials, a human-approval
UI and the independent gate adapters that produce real review evidence,
regional material editor, remaining typed edit executors, target-runtime
probes, real challenger weights/corpus and any consented cloud provider
adapter. They remain intentionally unclaimed until their slice gates pass.

## 1. Executive decision

Build Buffalo MLX 3.0 as a **secure, evidence-driven 3D asset compiler**, not as
a monolithic imitation of the Buffalo model.

The system SHALL transform real references plus an explicit delivery contract
into an immutable master asset, independently gated derivatives and a complete
evidence ledger. Semantic reasoning may propose parts, edits and routes. Only
deterministic policy and named human review may promote an asset.

The architecture SHALL combine the best verified ideas from:

- Buffalo: shared 3D understanding, grounded parts, source-conditioned editing,
  staged specialization and evidence that generation data can improve editing;
- current Xreality: native MLX Shape/Paint, sequential Metal execution,
  transactional simplification, GLB/PBR validation and Apple-aware admission;
- production DCC: reversible Blender operations, master-to-derivative baking,
  canonical renders and target-runtime round trips;
- current research: pixel-to-3D correspondence, illumination separation,
  confidence masks, multiview consistency and part/material-aware generation;
- Karpathy-style engineering: explicit assumptions, minimal mechanisms,
  surgical changes and tests that define success before implementation.

## 2. Goals and non-goals

### 2.1 Goals

G-01. Improve structural fidelity without hiding uncertainty.  
G-02. Make every expensive phase resumable, reproducible and independently
replaceable.  
G-03. Prevent memory pressure, corrupt outputs, unapproved network transfer and
silent quality degradation.  
G-04. Preserve semantic parts and material regions across edits and LODs.  
G-05. Support localized geometry and PBR edits without regenerating accepted
regions.  
G-06. Produce GLB/glTF and optional USDZ assets that pass the actual target
runtime.  
G-07. Create an arena where a challenger can replace a champion only with
measured, repeatable evidence.  
G-08. Keep the core useful offline on Apple Silicon; web support remains an
explicitly consented exception.

### 2.2 Non-goals for this phase

NG-01. Train an 87M-sample multimodal foundation model.  
NG-02. Claim use of unreleased Buffalo weights or code.  
NG-03. Implement unrestricted natural-language mesh editing.  
NG-04. Promise metrically accurate CAD from a single image.  
NG-05. Replace expert retopology for deformation-critical production assets.  
NG-06. Treat splats, NeRFs, depth maps or visually plausible renders as
production mesh equivalents.  
NG-07. Automatically upload customer references or enable paid APIs.

## 3. Paper findings translated into design decisions

| Buffalo finding | Adopt | Strengthen or reject |
|---|---|---|
| VLM + 3D DiT share semantic conditioning | separate Understanding Plane and Synthesis Plane | VLM never owns promotion or factual evidence state |
| XYZ, normals and RGB form structure/appearance tokens | use a canonical evidence representation | add scale, visibility, camera, confidence, material region and provenance |
| Q-Former compresses 3D to 512 tokens | use bounded semantic summaries | do not discard full-resolution deterministic evidence used by gates |
| boxes use 128 coordinate bins | boxes may seed coarse targeting | add oriented boxes, masks, component sets, surface IDs and confidence; AABB alone is insufficient |
| edit/part generation condition on source object | preserve source as immutable base and apply delta candidates | prove unchanged-region preservation geometrically and materially |
| outside-box voxel replacement preserves exterior | use explicit protected-region constraints | reject hard replacement as sole consistency guarantee; boundary and hidden-interior effects must be tested |
| one architecture serves QA/generation/editing/parts | share contracts and representations | keep runtime services isolated to reduce coupling, memory and blast radius |
| staged pretraining then specialization | use staged engineering rollout and champion/challenger lanes | no joint training until datasets, licenses and benchmarks exist |
| more text-to-3D data improves editing | reuse accepted assets and synthetic mutations for regression tests | never label synthetic pairs as real evidence; prevent feedback-loop contamination |
| data quality and scale remain limiting | build a curated evidence corpus first | quality, provenance and hard cases outrank raw volume |
| texture editing is future work | make synchronized regional PBR editing first-class | block master if albedo improves while MR/normal disagree |
| cascaded AR + DiT is hard to scale | define clean interfaces and checkpoints | investigate unified models only behind the same stage contracts |

## 4. System invariants

I-01. One heavy Metal consumer at a time.  
I-02. Every artifact is content-addressed and immutable after acceptance.  
I-03. A synthetic or inferred observation never becomes `measured`.  
I-04. `reject`, `attention` and `not_measured` never collapse into `pass`.  
I-05. A failed derivative never overwrites its accepted parent.  
I-06. Unchanged protected regions must pass geometry, UV and material-delta
gates after an edit.  
I-07. No external transfer or spend without job-scoped consent.  
I-08. No provider/model/profile substitution without a new signed execution
decision.  
I-09. Automated metrics can reject; only a named human can promote `master`.  
I-10. A job can resume only when stage inputs, implementation revision and
policy version match its checkpoint.  
I-11. Security validation runs before parsing untrusted 3D packages in Blender
or a viewer.  
I-12. Reported resolution, seed, steps, model and backend equal execution facts.

## 5. Logical architecture

```text
                    CONTROL PLANE (small, deterministic)
 request -> Contract Compiler -> Policy Engine -> Stage Scheduler
                |                    |               |
                v                    v               v
 Evidence Ledger/Provenance     Consent/Budget   Resource Governor
                |                    |               |
                +------------ Event Journal --------+
                                     |
                    EXECUTION PLANE (isolated workers)
       +-------------+---------------+----------------+
       |             |               |                |
 Reference Worker  Shape Worker   Blender Worker   Paint/PBR Worker
       |             |               |                |
       +-------------+------ Artifact Store ----------+
                                     |
                         Validation / Render Workers
                                     |
                          Delivery + Runtime Probes
                                     |
                    OPTIONAL QUARANTINED PROVIDER ADAPTER
```

### 5.1 Control Plane

The Control Plane SHALL contain no model weights and SHALL remain responsive
while workers are killed. It owns state transitions, policy, consent,
provenance, cache admission and promotion.

### 5.2 Execution Plane

Every heavy phase SHALL run in a disposable subprocess with:

- explicit input/output directories;
- read-only accepted inputs;
- bounded CPU threads, memory and wall time;
- network denied by default;
- heartbeat and structured progress;
- graceful cancellation then forced termination;
- post-exit verification that memory pressure returned below threshold.

### 5.3 Understanding Plane

The Understanding Plane MAY use a local VLM or geometric helper to propose:

- category and material regions;
- semantic macro-parts and aliases;
- expected cardinalities and spatial relationships;
- uncertain or hidden regions;
- localized edit targets.

It SHALL emit proposals with confidence and provenance. The Contract Compiler
shall validate these against category schemas and user evidence. A proposal is
not a measurement.

### 5.4 Synthesis Plane

Shape and Paint SHALL consume compiled contracts, not unrestricted prose. The
initial champion is the pinned Hunyuan3D 2.1 MLX path. TRELLIS.2 Apple,
Pixal3D, ReLi3D and later candidates SHALL implement the same provider
interface before entering shadow evaluation.

### 5.5 Validation Plane

Validation SHALL be independent of the generating provider. It combines pure
parsers, mesh metrics, Blender headless renders, glTF Validator, USD tools and
target-runtime probes. Provider self-scores SHALL be recorded only as
diagnostic metadata.

## 6. Canonical data contracts

All schemas SHALL use JSON Schema, `schema_version`, UTC timestamps, canonical
JSON serialization and SHA-256. Unknown fields SHALL be rejected in control
contracts and preserved-but-untrusted in provider metadata.

### 6.1 `JobContract`

```json
{
  "schema_version": 3,
  "job_id": "uuidv7",
  "intent": {
    "quality": "preview|mobile|xr|hifi|master",
    "targets": ["glb"],
    "face_budget": 200000,
    "texture_budget": 2048,
    "deadline_seconds": 1800
  },
  "evidence_manifest_hash": "sha256:...",
  "semantic_contract_hash": "sha256:...",
  "material_contract_hash": "sha256:...",
  "execution_policy_hash": "sha256:...",
  "network": {"allowed": false, "consent_id": null},
  "economy": {"currency": "USD", "maximum": 0, "auto_refill": false}
}
```

### 6.2 `EvidenceObservation`

Required fields: `observation_id`, `source_asset_hash`, `kind`, `camera`,
`visibility`, `region`, `value`, `confidence`, `evidence_class`, `producer`,
`license`, `privacy_class` and `created_at`.

`evidence_class` SHALL be one of `measured`, `user_asserted`, `inferred`,
`synthetic`, `not_measured`. Only imported real views and validated user
measurements may yield `measured`.

### 6.3 `SemanticPart`

```json
{
  "part_id": "stable-local-id",
  "canonical_name": "wheel",
  "aliases": ["tire assembly"],
  "count": {"minimum": 4, "maximum": 4},
  "critical": true,
  "thin": false,
  "relations": [{"type": "attached_to", "target": "axle"}],
  "localizers": {
    "aabb": null,
    "obb": null,
    "component_ids": [],
    "surface_mask_hash": null
  },
  "evidence_state": "not_measured",
  "confidence": 0.0
}
```

### 6.4 `StageManifest`

Required fields: stage/provider/model/code/weights revisions, input hashes,
configuration, seed, start/end, exit status, output hashes, metrics, peak RSS,
MLX active/peak, pressure samples, swap delta, network events and stderr hash.

### 6.5 `GateResult`

```json
{
  "gate_id": "geometry.finite.v1",
  "status": "pass|reject|attention|not_measured",
  "severity": "critical|major|minor|info",
  "metric": 0.0004,
  "threshold": {"operator": "lte", "value": 0.0005},
  "evidence_hashes": ["sha256:..."],
  "reason_code": "degenerate_ratio_within_master_limit",
  "safe_next_actions": []
}
```

### 6.6 `EditDelta`

An edit SHALL define target parts/regions, protected parts/regions, requested
geometry/material operations, tolerance budgets, source master hash and
expected invariants. It SHALL never contain an unrestricted executable script.

## 7. Job state machine

```text
DRAFT -> SEALED -> PREFLIGHTED -> RUNNING_STAGE
   ^        |            |              |
   |        v            v              v
 REVISE   REJECTED     BLOCKED       STAGE_PASSED
                                      |       |
                                      |       v
                                      |   STAGE_REJECTED -> RECOVERY_DECISION
                                      v
                                  NEXT_STAGE
                                      |
                               DELIVERY_CANDIDATE
                                  |          |
                               REJECTED   ACCEPTED
                                              |
                                  HUMAN_REVIEW_REQUIRED
                                       |          |
                                   NON_MASTER    MASTER
```

Transitions SHALL be compare-and-swap on `state_version`. Replaying an event
must be idempotent. Cancellation is legal from any nonterminal running state.
Recovery creates a new attempt linked to the failed attempt; it never edits
history.

## 8. Pipeline specifications

### P0 - Intake and trust boundary

Inputs: local files and user intent.  
Outputs: sanitized evidence package and draft contract.

Requirements:

- R-P0-01 reject path traversal, symlinks escaping the job, oversized archives,
  recursive packages and unsupported MIME/extension mismatches;
- R-P0-02 decode images with bounded dimensions/pixels and strip active or
  unnecessary metadata while preserving provenance separately;
- R-P0-03 classify privacy and license before any provider routing;
- R-P0-04 preserve originals read-only; derive normalized copies;
- R-P0-05 show missing evidence and achievable quality before execution.

Acceptance: malicious corpus causes no external write, network event, code
execution or control-process crash.

### P1 - Reference laboratory

Produce foreground masks, canonical crop, color-managed copies, camera/pose
hypotheses, scale clues and a visibility matrix.

- Real views SHALL retain distinct IDs.
- Synthetic turntables SHALL be tagged synthetic and excluded from real-view
  coverage.
- Conflicting scale or camera estimates SHALL yield `attention`.
- Preprocessing candidates SHALL be compared against the untouched reference;
  destructive loss of thin parts rejects the candidate.

### P2 - Semantic and material compilation

Build a category-specific macro-part graph and material-region graph. Use the
Buffalo insight of language-grounded parts, but compile them into stable IDs,
relationships and multiple localizers.

- Open-vocabulary names SHALL be normalized to an object-local mutually
  exclusive vocabulary where possible.
- Components MAY be grouped into one semantic macro-part; grouping confidence
  and raw component membership SHALL remain inspectable.
- Critical count contradictions SHALL block master generation.
- Material regions SHALL not be inferred from a single global label.

### P3 - Resource admission and scheduling

Admission SHALL use measured p95 stage profiles plus safety margin, current
pressure and projected swap. Unknown configurations start conservative.

- reserve OS/headroom before loading weights;
- cap retries and cumulative wall time;
- never run Shape/Paint/seeds concurrently;
- force subprocess recycling if verified memory release fails;
- expose an actionable blocked state instead of hanging the UI.

### P4 - Shape synthesis

Generate one shape candidate using the current champion. For `master`, a second
sequential seed MAY run only when real evidence is sufficient and policy admits
it. Selection SHALL use the full gate vector, not a VLM preference.

Required outputs: raw mesh, normalized mesh, stage manifest, canonical geometry
renders and failure evidence.

### P5 - Geometry, topology and semantic-part gate

Evaluate:

- finite vertices/normals and index bounds;
- degenerate/non-manifold/boundary metrics by asset policy;
- winding, components, self-intersection sampling and volume when applicable;
- silhouettes and depth against every real calibrated view;
- semantic counts, thin-part survival and relational plausibility;
- physical scale and contact/support constraints;
- internal-wall/“vase” detection for printable solids.

A VLM MAY flag suspicious regions for review. It SHALL NOT clear a deterministic
failure.

### P6 - Transactional repair, retopo and UV

Use Blender headless or pure mesh tools only through versioned operations.
Capture before/after fingerprints. Protect part/material borders, UV seams,
hard normals and authored holes.

The candidate passes only if it improves the target defect and causes no
critical regression. Global merge, remesh, component deletion and decimation
are prohibited without an explicit operation contract.

### P7 - Paint and regional PBR

Run Paint only after Shape has exited and memory is safe. Produce baseColor,
roughness, metalness, normal/bump, optional AO and per-region confidence.

- synchronize all maps after reference locking or local correction;
- preserve unobserved texels as uncertain, not measured;
- reject baked highlights/shadows in albedo;
- require physically plausible region behavior;
- support material extensions only after target-runtime validation.

### P8 - Localized editing

Adopt Buffalo source-object conditioning as a delta workflow:

1. freeze the accepted source master;
2. compile target and protected masks using part IDs + surfaces, not only AABB;
3. generate or apply a candidate delta;
4. feather/test boundary zones while preserving hard semantic boundaries;
5. compare protected geometry, UV and every PBR map against source;
6. reject drift outside tolerance;
7. store source, delta and result hashes.

Edits SHALL be typed: `add_part`, `remove_part`, `reshape_part`,
`replace_material`, `retexture_region`, `transform_part`. Free-form requests
must compile to these types or remain unsupported.

### P9 - Validation and canonical review

Render at minimum:

- unlit/base-color;
- neutral front and both quarters;
- grazing light;
- wireframe and semantic-part colors;
- alpha checker for cards and transmission checker for glass;
- before/after protected-region diff for edits.

Require glTF Validator, Blender round-trip and target viewer/runtime. USDZ
requires normalized packaging and `usdchecker --arkit --strict`.

### P10 - Derivatives and delivery

Create LOD/mobile/XR/web/USDZ derivatives from the accepted master. Every
derivative SHALL retain lineage, rebake textures when topology changes and pass
its target-specific budget/gates. Compression SHALL be reversible at the build
level and tested in the actual decoder.

### P11 - Learning and arena

Persist only sanitized metrics, contracts and consented artifacts. Failed and
hard examples are more valuable than unfiltered volume.

- split corpus by source identity to prevent leakage;
- keep real, synthetic and provider outputs as separate strata;
- pin benchmark prompts, views, policies and reviewer protocol;
- use sequential seeds and confidence intervals;
- require blind human review for subjective lanes;
- prevent generated outputs from recursively becoming unquestioned ground
  truth.

## 9. Skill orchestration specification

Skills SHALL provide bounded procedure, never authority. Load only one phase
bundle unless the decision spans a declared boundary.

| Phase bundle | Trigger | Inputs | Outputs | Unload condition |
|---|---|---|---|---|
| Evidence Surgeon | intake, ambiguity, routing | references + intent | evidence/semantic drafts | contracts sealed |
| Shape Assembly TD | shape/topology/parts | contracts + mesh | gate vector/repair candidate | geometry accepted/rejected |
| Blender Operator | UV/bake/repair/render | immutable source + operation | candidate + `.blend` evidence | Blender process exited |
| PBR Material Surgeon | Paint/material/edit | mesh + region graph | synchronized maps/material gates | textures sealed |
| Production Gatekeeper | promotion/delivery | all manifests | promotion decision | report signed |
| Runtime Optimizer | web/XR/game/USDZ | accepted master + target | gated derivative | runtime probe complete |
| Cloud Challenger | explicit exceptional route | consent + budget + sanitized input | quarantined candidate | credentials cleared and cost reconciled |

Third-party skills SHALL pass supply-chain review: source identity, pinned
commit, license, diff inspection, no secret discovery, no autonomous install,
no unbounded shell and no hidden network. Only the necessary concepts or
scripts enter the repository.

## 10. Security and threat model

### 10.1 Assets protected

- customer images, geometry and identity;
- local credentials and provider tokens;
- workstation availability and unified memory;
- accepted masters and evidence history;
- cost budgets and API accounts;
- truthfulness of quality/provenance reports.

### 10.2 Threats and mandatory controls

| Threat | Control | Security test |
|---|---|---|
| malicious GLB/USD/ZIP | size/count/depth limits, safe parser first, sandboxed Blender, no scripts/drivers | fuzz corpus, zip bomb, invalid accessors, cyclic nodes |
| Blender code execution | never open untrusted `.blend`; disable auto-run; import sanitized exchange formats in isolated process | crafted driver/script fixture cannot execute |
| path traversal/symlink | canonical job root, `openat`-style safe writes, reject escaping links | traversal and race fixtures |
| model/skill supply-chain compromise | pinned commit/hash, license manifest, quarantine, offline cache | tampered weight/script hash fails preflight |
| prompt injection in metadata/textures | treat names, extras and provider text as data; never concatenate into authority instructions | adversarial filenames/extras do not alter policy |
| memory denial of service | preflight, watchdog, caps, cancellation, subprocess | OOM injection preserves control plane and checkpoint |
| silent cloud exfiltration | deny network by default, job-scoped consent, host allowlist, event log | packet attempt without consent is blocked/audited |
| runaway spend | estimate ceiling, atomic budget reservation, no auto-refill, retry cap | concurrent attempts cannot exceed reserved budget |
| result poisoning | untrusted provider lane, same independent gates, provenance | provider “pass” cannot bypass local reject |
| evidence forgery | content hashes, append-only journal, evidence classes | mutation invalidates lineage and resume |
| PII/biometric misuse | explicit consent, local default, retention policy, likeness warnings | deletion/retention and export audit |
| license contamination | code/weights/output license registry and delivery compatibility gate | incompatible license blocks commercial preset |

### 10.3 Secrets

Provider tokens SHALL reside in OS keychain or an injected ephemeral file
descriptor, never project `.env`, logs, command arguments, manifests or crash
dumps. Provider workers receive only the credential scoped to their host and
job. Redaction tests are mandatory.

### 10.4 Network policy

Local workers have no network entitlement. Provider adapters run separately
with DNS/host allowlists, TLS verification, timeouts, byte limits and explicit
upload manifest. Redirects to unapproved hosts fail closed.

## 11. Quality gates

Promotion is a conjunction:

```text
deliverable = input & security & geometry & parts & topology & UV & texture
              & material & memory & package & runtime & license
master      = deliverable & sufficient_real_evidence & canonical_review
              & named_human_approval
edit        = deliverable & target_change & protected_region_preservation
```

Thresholds SHALL live in a versioned policy registry by asset category and
quality profile. Until calibrated, a threshold is `unmeasured`, not guessed.
Policy changes require replay against the golden corpus before activation.

## 12. Hypotheses and falsification plan

| ID | Hypothesis | Experiment | Falsification/decision |
|---|---|---|---|
| H-01 | semantic part contracts reduce missing critical parts | same 30 hard inputs, contract on/off, two sequential seeds | reject if improvement is within seed variance or harms geometry |
| H-02 | surface masks + OBB outperform AABB-only edit localization | 20 edits with narrow/rotated parts; measure target success and protected drift | reject if boundary/protected drift is not significantly lower |
| H-03 | source-conditioned delta editing is cheaper and safer than full regeneration | 20 local edits; compare time, peak memory, outside-region change | reject if retries erase savings or hidden topology breaks |
| H-04 | regional synchronized PBR improves relighting without losing reference fidelity | blind review + photometric consistency across neutral lights | reject if front similarity rises but physical/material lane regresses |
| H-05 | subprocess isolation improves reliability enough to justify load overhead | 30-job soak with injected failures versus in-process baseline | reject if no recovery gain or latency exceeds declared budget |
| H-06 | Blender deterministic repair fixes targeted defects without collateral damage | defect corpus with known ground truth | prohibit any operation whose critical regression rate is nonzero |
| H-07 | TRELLIS.2 Apple can beat Hunyuan MLX on a useful profile | sealed arena across 16/24/32/64 GB Macs | remain challenger if memory, reproducibility or any critical lane loses |
| H-08 | synthetic multiview helps conditioning but cannot replace real evidence | single real vs real multiview vs synthetic augmentation | retain only if output improves; master evidence rule never changes |
| H-09 | confidence-weighted multi-view projection reduces seams | paired corpus with calibrated cameras | reject if seam gains cost alignment or texel coverage |
| H-10 | stage caching cuts median iteration time without stale artifacts | edit/retry workload with hash mutation tests | reject cache strategy on any false hit |

Experiments SHALL declare sample, metric, minimum useful effect and stopping
rule before execution. Negative results remain in the decision log.

## 13. Verification strategy

### 13.1 Test pyramid

1. schema/property tests for contracts, hashes and transitions;
2. pure geometry/material unit tests;
3. golden malformed assets and security fuzzing;
4. worker integration tests with fake weights/providers;
5. deterministic micro-assets for each Blender operation;
6. end-to-end offline jobs on representative Macs;
7. target-runtime and human review;
8. 30-job soak plus cancellation/restart/OOM injection.

### 13.2 Mandatory adversarial corpus

- NaN/Inf vertices, invalid indices, zero-area faces and cyclic scene graph;
- hundreds of components, giant textures and decompression bombs;
- hollow/vase solid, inverted normals, internal duplicate shells;
- missing wheel/hook/finger, fused limbs and lost thin cable;
- UV outside policy, overlaps, zero-area UV and insufficient gutter;
- metallic rust/skin, opaque fake glass, baked highlights and swapped MR channels;
- albedo-only edit with stale normal/MR;
- malicious filenames, GLB extras and provider messages containing instructions;
- external texture URIs and redirects;
- cancellation at every checkpoint and crash during atomic commit.

### 13.3 Performance protocol

Report cold and warm p50/p95, stage wall time, peak RSS, MLX active/peak, swap
delta, energy when observable, artifact size and cache hit. Run seeds
sequentially. Never compare different resolutions, revisions or gates under one
quality label.

## 14. Observability and audit

Use structured events with stable reason codes. Logs SHALL not contain image
content, secrets or unrestricted prompts by default. The UI must answer:

- what is running and why;
- which model/revision/profile was admitted;
- current memory/pressure and cancellation state;
- which lane failed and with what evidence;
- safest next action and whether it costs money or sends data;
- lineage from input to delivered asset.

Metrics remain local unless telemetry is separately consented. Exportable job
reports SHALL be self-contained and redactable.

## 15. Rollout plan

### 15.0 Baseline-to-target traceability

This matrix prevents the SDD from presenting targets as existing behavior.

| Capability | Baseline evidence | 3.0 gap |
|---|---|---|
| semantic templates and part expectations | `engine/buffalo_strategy.py`, `engine/asset_director.py` | evidence-backed localization, stable part IDs and correction workflow |
| assembly fingerprint and transactional simplification | `validate_assembly_preservation` and server fallback | semantic surface mapping, self-intersection/internal-wall gates and policy calibration |
| Shape/Paint sequencing and cache cleanup | `engine/server.py`, Paint services and tests | opt-in Shape worker boundary and verified release; default promotion, resumable checkpoints and event journal remain staged |
| memory admission/watchdog for Agentic Paint | `engine/agentic_paint_service.py` | common resource governor for every heavy provider and chip-specific p95 registry |
| native Paint/reference fidelity gates | `engine/reference_projection.py` | synchronized regional PBR confidence and protected-map edit diffs |
| structural GLB/PBR validation | `engine/pbr_glb.py`, benchmark arena tests | safe untrusted parser, Khronos validator integration and adversarial asset corpus |
| Buffalo metadata in GLB | `embed_strategy_metadata` | canonical versioned schemas, immutable evidence ledger and cryptographic lineage across derivatives |
| USDZ strict validation path | server/report architecture | target-device matrix, policy-driven packaging and atomic delivery |
| benchmark provider registry | `engine/benchmark_arena.py` and tests | sealed representative corpus, blind review, statistical promotion and shadow mode |
| optional online behavior | isolated repair/download behaviors exist | global network deny, consent object, host allowlist, privacy manifest and atomic cost reservation |

Any implementation issue SHALL cite one SDD requirement/invariant and one
verification artifact. A change without both is not part of Buffalo MLX 3.0.

### Slice A - Truthful contracts and state machine

Implement schemas, append-only journal, reason codes and v1-report migration.
No model change. Exit: replay/idempotency/property tests pass.

### Slice B - Worker isolation and memory safety

Move Shape, Paint and Blender behind disposable workers; add admission,
watchdog, cancellation and checkpointing. Exit: injected OOM/crash cannot lose
accepted work or freeze control plane.

### Slice C - Independent validation plane

Add safe parser, Blender canonical renders, glTF Validator and adversarial
corpus. Exit: every seeded critical defect is rejected by the intended lane.

### Slice D - Semantic parts and regional materials

Add part/material graphs, visibility/confidence and human correction UI. Exit:
contracts are stable across reruns and corrections preserve provenance.

### Slice E - Localized delta editing

Ship one typed edit first: `replace_material`; then `remove_part`; then
`reshape_part`. Exit per edit: target success plus protected-region gates on the
golden corpus. Do not launch all edit types together.

### Slice F - Derivatives and runtime certification

Add LOD/rebake/compression/USDZ profiles. Exit: Blender, Three.js and macOS
runtime matrix passes.

### Slice G - Challenger arena

Benchmark pinned TRELLIS.2 Apple first; later Pixal3D/ReLi3D techniques. Run in
shadow mode before any promotion. Exit: documented decision, including a valid
decision to retain Hunyuan.

### Slice H - Optional cloud adapter

Only after A-G are stable. Begin with one provider and a hard USD 0 default.
Exit: consent, privacy, cost reservation/reconciliation and kill switch pass.

## 16. Definition of Done

This architecture phase is complete only when:

1. all invariants I-01 through I-12 have automated enforcement tests;
2. 30 heterogeneous offline jobs complete without Metal overlap or false
   promotion;
3. cancellation/crash/OOM resumes from the last valid checkpoint;
4. malicious asset tests cannot escape the job sandbox or execute Blender code;
5. semantic critical-part regressions and hollow printable solids are detected;
6. regional PBR edits preserve aligned maps and protected regions;
7. every derivative traces to an immutable accepted master;
8. master promotion requires sufficient real evidence and named human approval;
9. provider calls are impossible without consent and atomic budget reservation;
10. reports reproduce actual revisions, settings, memory, costs and hashes;
11. champion/challenger decisions are repeatable on the sealed corpus;
12. documentation distinguishes implemented, target, research and rejected
    paths.

## 17. Open decisions requiring measurement

- exact p95 admission tables per Apple chip/RAM;
- whether Hunyuan Shape should remain resident between same-profile jobs;
- useful granularity and storage cost of surface-level evidence masks;
- OBB/surface-mask representation compatible with Blender and glTF metadata;
- best deterministic self-intersection and protected-surface metrics at scale;
- whether TRELLIS.2 Apple achieves end-to-end MLX parity and safe memory on
  24-GB systems;
- which PBR confidence estimator provides measurable value without a CUDA-only
  dependency;
- retention schedule for user assets, canonical renders and rejected attempts.

No open decision may be resolved by a marketing claim or a single screenshot.

## 18. Primary references

- Local `Hunyuan3D-Buffalo 1.0.pdf`, especially Sections 3.4-4.2 and 6.
- `BUFFALO_MLX_ARCHITECTURE.md`.
- `engine/buffalo_strategy.py`, `engine/asset_director.py`,
  `engine/server.py`, `engine/paint_service.py`, `engine/pbr_glb.py` and current
  tests as implementation baseline.
- Khronos glTF 2.0 and glTF Validator.
- OpenUSD/RealityKit validation tools.
- Pinned upstream model repositories only after supply-chain review.
