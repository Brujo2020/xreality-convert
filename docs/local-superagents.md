# Local Superagents

## Implemented

Xreality Convert ships a file-backed `Xreality Core` skill pack. Electron main validates the catalog, rejects duplicate skills and unknown executors, compiles a deterministic DAG for each workflow, owns mission state, and publishes bounded snapshots to the renderer.

The current specialists are:

- Reference Director and Input Sentinel
- Shape Architect and Geometry Critic
- XR Delivery and PBR Materialist
- PBR Inspector, Image Output Gate, and Evidence Card

Mission events come from the real Ollama and Hunyuan execution paths. Repeated backend polls for the same skill are idempotent. Mission metadata is journaled locally without prompts, images, paths, or model secrets.

## Offline boundary

- Planning and orchestration do not call a model, cloud API, shell, or arbitrary executable.
- Inference uses loopback-only local providers.
- Initial runtime installation, model pulls, and missing weight downloads still require network access.
- A skill can invoke only an executor present in the hardcoded allowlist.
- The legacy model-generated JSCAD executor is not exposed to the renderer and is hard-disabled in Electron main.

## Skill contract

The catalog is `skills/xreality-core.json` with schema version `1`. Adding JSON alone cannot grant a new capability: a new executor must also be added to the main-process allowlist, mapped into a recipe, connected to a real runtime event, and covered by tests.

## Current limits

- Missions do not yet resume across an application restart.
- The journal is an event trail, not a replay UI.
- Approvals and exported artifacts do not yet use opaque IDs or a dedicated permission broker.
- Renderer file operations are root-confined, but opaque artifact IDs are still pending.
- Loopback authentication, strict subprocess environment allowlists, and dependency pinning remain security work.
- Automated tests do not prove live MLX inference, final rendered PBR fidelity, signing, or notarization.

## Verification

```bash
npm run test:tools
npm run build:vite
node --check electron/main.js
node --check electron/preload.js
git diff --check
```
