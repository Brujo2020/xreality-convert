# Local Toolchain Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un registry local que detecte, clasifique y muestre herramientas 3D instaladas sin descargarlas, ejecutar shell ni exponer paths al renderer.

**Architecture:** Electron main posee discovery y cache de capabilities; preload expone solo un IPC cerrado `tools:list`; React presenta disponibilidad y propósito. Python embebido aporta Trimesh, PyMeshLab, xatlas y pygltflib. Khronos glTF Validator, glTF-Transform, KTX y Blender son adaptadores opcionales: `missing` nunca activa descarga ni fallback.

**Tech Stack:** Electron 33 CommonJS main/preload, Node 20+ core (`child_process`, `fs`, `path`), React 18, Tailwind CSS, Node test runner.

## Global Constraints

- Local-only: discovery no usa red, package managers ni URLs.
- Renderer recibe IDs, versiones, capabilities e install hints; nunca executable paths, entorno o stdout crudo.
- Probes usan `spawn` con `shell:false`, argumentos constantes, timeout 2 s y output combinado máximo 8 KiB.
- Estados cerrados: `ready | missing | blocked`.
- `ready` informa capacidad; no autoriza procesar un asset ni sustituye `StageAdmissionReceipt`.
- No modificar `engine/setup.sh`, instalar paquetes o descargar modelos en este plan.
- Tools iniciales: `trimesh`, `pymeshlab`, `xatlas`, `pygltflib`, `gltf_validator`, `gltf-transform`, `ktx|toktx`, `blender`.

---

### Task 1: Registry puro y probes acotados

**Files:**
- Create: `electron/tool-registry.js`
- Test: `electron/tool-registry.test.js`

**Interfaces:**
- Consumes: `enginePython: string`, `pathEnv?: string`, dependencias inyectables para test.
- Produces: `discoverLocalTools(options) -> Promise<{ checkedAt, tools[] }>` y `createToolRegistry(options) -> { list({ force? }) }`.

- [ ] **Step 1: Write the failing tests**

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { createToolRegistry, redactProbeResult } = require('./tool-registry');

test('registry returns closed public descriptors without executable paths', async () => {
  const registry = createToolRegistry({
    enginePython: '/private/runtime/python',
    now: () => 1000,
    probe: async ({ id }) => id === 'trimesh'
      ? { ok: true, version: '4.7.1', executablePath: '/private/runtime/python' }
      : { ok: false, reason: 'not_found' },
  });
  const result = await registry.list();
  assert.equal(result.tools.find((tool) => tool.id === 'trimesh').status, 'ready');
  assert.equal(JSON.stringify(result).includes('/private/runtime'), false);
});

test('registry caches probes until forced', async () => {
  let calls = 0;
  const registry = createToolRegistry({
    enginePython: '/runtime/python',
    now: () => 1000,
    probe: async () => { calls += 1; return { ok: false, reason: 'not_found' }; },
  });
  await registry.list();
  await registry.list();
  assert.equal(calls, 8);
  await registry.list({ force: true });
  assert.equal(calls, 16);
});

test('probe errors are normalized and bounded', () => {
  const result = redactProbeResult({ ok: false, reason: 'spawn_error', detail: 'x'.repeat(9000) });
  assert.equal(result.reason, 'probe_failed');
  assert.equal('detail' in result, false);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `node --test electron/tool-registry.test.js`

Expected: FAIL with `Cannot find module './tool-registry'`.

- [ ] **Step 3: Implement the registry**

Create frozen definitions for the eight tools. Python probes call the fixed engine interpreter with `-c` and `importlib.metadata.version()`. Binary probes resolve only PATH entries and fixed macOS application candidates, then call fixed version args. `redactProbeResult()` returns only `{ok, version?, reason?}`. `createToolRegistry()` caches for 30 seconds and maps raw results to:

```js
{
  id: 'trimesh',
  label: 'Trimesh',
  category: 'geometry',
  status: 'ready',
  version: '4.7.1',
  capabilities: ['inspect_mesh', 'repair_basic', 'convert_stl'],
  bundled: true,
  installHint: null,
}
```

Use `spawn(executable, args, { shell: false, stdio: ['ignore', 'pipe', 'pipe'] })`; kill after 2,000 ms; truncate collected bytes at 8,192.

- [ ] **Step 4: Run tests to verify pass**

Run: `node --test electron/tool-registry.test.js`

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add electron/tool-registry.js electron/tool-registry.test.js
git commit -m "feat: add local 3d tool registry"
```

### Task 2: IPC cerrado y bridge browser

**Files:**
- Modify: `electron/main.js`
- Modify: `electron/preload.js`
- Modify: `src/main.jsx`
- Test: `electron/tool-registry.test.js`

**Interfaces:**
- Consumes: `createToolRegistry({ enginePython })` from Task 1.
- Produces: `window.localTools.list({ force?: boolean })` returning the public registry snapshot.

- [ ] **Step 1: Add failing contract assertions**

Extend the registry test to assert invalid `force` values normalize to `false` and public results contain no `path`, `command`, `stdout`, `stderr` or environment fields.

- [ ] **Step 2: Run the focused test**

Run: `node --test electron/tool-registry.test.js`

Expected: FAIL on the new closed-schema assertion.

- [ ] **Step 3: Wire main and preload**

In `electron/main.js`, instantiate after `HUNYUAN_SERVER_DIR` is known:

```js
const { createToolRegistry } = require('./tool-registry');
const localToolRegistry = createToolRegistry({
  enginePython: path.join(HUNYUAN_SERVER_DIR, 'venv', 'bin', 'python'),
});

ipcMain.handle('tools:list', async (_event, payload = {}) => (
  localToolRegistry.list({ force: payload?.force === true })
));
```

In `electron/preload.js` expose only:

```js
contextBridge.exposeInMainWorld('localTools', {
  list: (options = {}) => ipcRenderer.invoke('tools:list', { force: options.force === true }),
});
```

In `src/main.jsx`, add a deterministic development bridge with the same schema and four bundled tools marked `ready`, optional tools `missing`.

- [ ] **Step 4: Run registry tests and Vite build**

Run: `node --test electron/tool-registry.test.js && npm run build:vite`

Expected: tests PASS; Vite exits 0.

- [ ] **Step 5: Commit**

```bash
git add electron/main.js electron/preload.js src/main.jsx electron/tool-registry.test.js
git commit -m "feat: expose local tool capabilities"
```

### Task 3: Estado derivado y UI accesible

**Files:**
- Create: `src/lib/toolSummary.js`
- Create: `src/lib/toolSummary.test.js`
- Create: `src/components/LocalToolchainStatus.jsx`
- Modify: `src/components/Header.jsx`
- Modify: `src/App.jsx`

**Interfaces:**
- Consumes: `window.localTools.list()` snapshot.
- Produces: `summarizeTools(tools)` and `LocalToolchainStatus({ snapshot, checking, onRefresh })`.

- [ ] **Step 1: Write failing summary tests**

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { summarizeTools } from './toolSummary.js';

test('summarizes ready bundled and optional tools', () => {
  const summary = summarizeTools([
    { id: 'trimesh', status: 'ready', bundled: true },
    { id: 'blender', status: 'missing', bundled: false },
  ]);
  assert.deepEqual(summary, { ready: 1, bundledReady: 1, missing: 1, blocked: 0, total: 2 });
});

test('unknown status fails closed as blocked', () => {
  assert.equal(summarizeTools([{ status: 'surprise' }]).blocked, 1);
});
```

- [ ] **Step 2: Run test to verify failure**

Run: `node --test src/lib/toolSummary.test.js`

Expected: FAIL with module-not-found.

- [ ] **Step 3: Implement summary and component**

`LocalToolchainStatus` renders a header button `N/8 tools listas`. Its popover groups `ready`, `missing`, `blocked`; each row shows label, capabilities and whether it is bundled or optional. Missing tools show a text-only hint; no install button. Button uses `aria-expanded`, popover uses `role="status"`, Escape closes it, and refresh is disabled while checking.

In `App.jsx`, add `toolSnapshot`/`toolsChecking`, `checkLocalTools(force=false)`, call it on mount, and pass props through `Header`. `checkStatus()` refreshes Ollama only; the tool popover owns its explicit refresh to avoid spawning probes every five seconds.

- [ ] **Step 4: Run tests and build**

Run: `node --test src/lib/toolSummary.test.js electron/tool-registry.test.js && npm run build:vite`

Expected: all tests PASS; Vite exits 0.

- [ ] **Step 5: Commit**

```bash
git add src/lib/toolSummary.js src/lib/toolSummary.test.js src/components/LocalToolchainStatus.jsx src/components/Header.jsx src/App.jsx
git commit -m "feat: show local 3d toolchain status"
```

### Task 4: Verification integrada y documentation

**Files:**
- Modify: `package.json`
- Create: `docs/local-toolchain.md`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: repeatable `npm run test:tools` and operator documentation.

- [ ] **Step 1: Add test script**

Add:

```json
"test:tools": "node --test electron/tool-registry.test.js src/lib/toolSummary.test.js"
```

- [ ] **Step 2: Document exact tiers**

Document bundled vs optional tools, capabilities, local-only discovery, missing-tool behavior and explicit non-goals. Include official sources for Khronos glTF Validator, glTF-Transform, KTX-Software and Blender. State that availability is not admission to run against an asset.

- [ ] **Step 3: Execute full focused verification**

Run: `npm run test:tools && npm run build:vite`

Expected: tests and build exit 0.

- [ ] **Step 4: Browser smoke**

Open `http://localhost:5173/`; verify header shows `4/8 tools listas`, popover opens/closes by mouse and Escape, four bundled tools are ready, optional tools are missing, and refresh does not alter Ollama/generation state.

- [ ] **Step 5: Review staged boundary and commit**

```bash
git diff --check
git status --short
git add package.json docs/local-toolchain.md
git commit -m "docs: document local 3d toolchain"
```

Expected boundary: only files enumerated in Tasks 1-4.

