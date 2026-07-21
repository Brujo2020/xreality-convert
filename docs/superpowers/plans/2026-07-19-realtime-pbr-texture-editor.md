# Realtime PBR Texture Editor Implementation Plan

Estado: cerrado como plan aprobado el 2026-07-19; implementación queda para la próxima evolución.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate local MLX Paint stage that preserves the original mesh, previews editable PBR material changes in real time, and exports the exact selected original or textured GLB.

**Architecture:** Python owns Paint inference, PBR validation, and GLB materialization. Electron main owns artifact paths and exposes ID-only IPC. React holds non-destructive material state; Three.js keeps original and Paint scenes loaded and applies reversible shader/material overrides. Every generated or exported artifact has lineage and a gate report.

**Tech Stack:** Electron 33, React 18, Three.js 0.185, FastAPI/Pydantic, MLX Hunyuan3D Paint, Pillow, pygltflib, Python `unittest`, Node `node:test`, Vite.

## Global Constraints

- macOS Apple Silicon, 24 GB unified memory; no CUDA-only dependency.
- Stable Paint provider is `dgrauet/Hunyuan3D-2.1-mlx@58e61ee`; do not add Pixal3D or TRELLIS.2 runtime.
- Preserve Shape file and SHA-256 exactly; Paint and Delivery are new files.
- Texture profiles are exactly `fast`, `balanced`, `quality`; default is `balanced`; no silent fallback.
- Texture sizes are 1024 for fast/balanced and 2048 for quality; 4K is out of scope.
- Renderer sends artifact IDs and bounded settings, never filesystem paths for new texture operations.
- `textureApplied` comes only from the final PBR gate.
- Color operations run in this order in sRGB: brightness, contrast around 0.5, Rec.709 saturation, tint blend, clamp.
- Sliders never invoke Paint inference.
- No success claim without Node tests, Python tests, Vite build, browser verification, and a real Paint smoke or an explicit blocked result.

---

## File Structure

**Create**

- `shared/material-color-vectors.json` — cross-runtime golden color vectors.
- `src/lib/materialSettings.js` — settings schema, clamping, appearance presets.
- `src/lib/materialSettings.test.js` — renderer contract tests.
- `src/lib/materialPreview.js` — Three.js material snapshot, shader patch, scene toggling.
- `src/lib/materialPreview.test.js` — preview behavior tests without WebGL.
- `src/lib/materialEditorState.js` — reducer for overlay and Paint lifecycle.
- `src/lib/materialEditorState.test.js` — reducer/persistence tests.
- `src/components/MaterialOverlay.jsx` — approved collapsible overlay.
- `engine/material_settings.py` — same color transform and bounds in Python.
- `engine/test_material_settings.py` — Python parity tests using shared vectors.
- `engine/pbr_glb.py` — PBR gate, embedded image access, materialization.
- `engine/test_pbr_glb.py` — synthetic GLB gate/materialization tests.
- `engine/paint_service.py` — profile mapping, lazy MLX Paint lifecycle.
- `engine/test_paint_service.py` — fake-pipeline profile and failure tests.
- `electron/artifact-registry.js` — owner-scoped artifact IDs and allowed-root validation.
- `electron/artifact-registry.test.js` — ownership/path/rehydration tests.

**Modify**

- `engine/server.py` — durable reference artifacts, texture jobs, materialize endpoint.
- `electron/main.js` — registry integration, texture polling, ID-only export.
- `electron/preload.js` — minimal texture IPC surface.
- `src/components/GltfViewer.jsx` — dual scene and live material preview.
- `src/components/ImageViewer.jsx` — overlay placement and texture actions.
- `src/App.jsx` — texture workflow, history, export selection.
- `package.json` — test scripts and package all engine Python modules.
- `engine/setup.sh` — install marker bump only if runtime files/dependencies changed.
- `docs/MANUAL.md` — user workflow, presets, memory errors, export semantics.

---

### Task 1: Cross-runtime material contract

**Files:**
- Create: `shared/material-color-vectors.json`
- Create: `src/lib/materialSettings.js`
- Create: `src/lib/materialSettings.test.js`
- Create: `engine/material_settings.py`
- Create: `engine/test_material_settings.py`
- Modify: `package.json`

**Interfaces:**
- Produces: `DEFAULT_MATERIAL_SETTINGS`, `APPEARANCE_PRESETS`, `normalizeMaterialSettings(input)`, `transformSrgb(rgb, settings)` in JS.
- Produces: `normalize_material_settings(value)` and `transform_srgb(rgb, settings)` in Python.
- Values use floats in `[0,1]`; RGB inputs and outputs are three-element arrays.

- [ ] **Step 1: Add golden vectors and failing JS tests**

```json
{
  "vectors": [
    {
      "name": "identity",
      "rgb": [0.2, 0.4, 0.6],
      "settings": {},
      "expected": [0.2, 0.4, 0.6]
    },
    {
      "name": "ordered-transform",
      "rgb": [0.2, 0.4, 0.6],
      "settings": {
        "brightness": 1.1,
        "contrast": 1.2,
        "saturation": 0.8,
        "tint": "#ff8000",
        "tintStrength": 0.25
      },
      "expected": [0.40704016, 0.44093036, 0.47384016]
    }
  ]
}
```

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import vectors from '../../shared/material-color-vectors.json' with { type: 'json' };
import { APPEARANCE_PRESETS, normalizeMaterialSettings, transformSrgb } from './materialSettings.js';

test('normalizes bounded material settings', () => {
  assert.deepEqual(normalizeMaterialSettings({ brightness: 9, metallic: -1 }).brightness, 1.5);
  assert.equal(normalizeMaterialSettings({ brightness: 9, metallic: -1 }).metallic, 0);
});

for (const vector of vectors.vectors) {
  test(`matches golden color vector: ${vector.name}`, () => {
    const actual = transformSrgb(vector.rgb, normalizeMaterialSettings(vector.settings));
    actual.forEach((value, index) => assert.ok(Math.abs(value - vector.expected[index]) < 1e-4));
  });
}

test('exposes the four approved appearance presets', () => {
  assert.deepEqual(Object.keys(APPEARANCE_PRESETS), ['natural', 'matte', 'glossy', 'metallic']);
});
```

- [ ] **Step 2: Run JS test and verify RED**

Run: `node --test src/lib/materialSettings.test.js`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `materialSettings.js`.

- [ ] **Step 3: Implement the JS contract**

```js
export const DEFAULT_MATERIAL_SETTINGS = Object.freeze({
  brightness: 1, contrast: 1, saturation: 1,
  tint: '#ffffff', tintStrength: 0,
  roughness: 0.6, metallic: 0,
});

export const APPEARANCE_PRESETS = Object.freeze({
  natural: {},
  matte: { brightness: 1, contrast: 0.98, saturation: 0.95, roughness: 0.9, metallic: 0 },
  glossy: { brightness: 1.03, contrast: 1.05, saturation: 1.02, roughness: 0.18 },
  metallic: { brightness: 0.95, contrast: 1.08, saturation: 0.9, roughness: 0.28, metallic: 0.9 },
});

const clamp = (value, min, max) => Math.min(max, Math.max(min, Number(value)));
const hexRgb = (hex) => [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255);

export function normalizeMaterialSettings(input = {}, paintDefaults = {}) {
  const value = { ...DEFAULT_MATERIAL_SETTINGS, ...paintDefaults, ...input };
  return {
    brightness: clamp(value.brightness, 0.5, 1.5),
    contrast: clamp(value.contrast, 0.5, 1.5),
    saturation: clamp(value.saturation, 0, 2),
    tint: /^#[0-9a-f]{6}$/i.test(value.tint) ? value.tint.toLowerCase() : '#ffffff',
    tintStrength: clamp(value.tintStrength, 0, 1),
    roughness: clamp(value.roughness, 0, 1),
    metallic: clamp(value.metallic, 0, 1),
  };
}

export function transformSrgb(rgb, settings) {
  let color = rgb.map((channel) => channel * settings.brightness);
  color = color.map((channel) => (channel - 0.5) * settings.contrast + 0.5);
  const luminance = color[0] * 0.2126 + color[1] * 0.7152 + color[2] * 0.0722;
  color = color.map((channel) => luminance + (channel - luminance) * settings.saturation);
  const tint = hexRgb(settings.tint);
  return color.map((channel, index) => clamp(channel * (1 - settings.tintStrength) + tint[index] * settings.tintStrength, 0, 1));
}
```

- [ ] **Step 4: Run JS test and verify GREEN**

Run: `node --test src/lib/materialSettings.test.js`

Expected: 4 tests, 0 failures.

- [ ] **Step 5: Add the failing Python parity test**

```python
import json, unittest
from pathlib import Path
from engine.material_settings import normalize_material_settings, transform_srgb

class MaterialSettingsTests(unittest.TestCase):
    def test_golden_vectors_match(self):
        vectors = json.loads(Path('shared/material-color-vectors.json').read_text())['vectors']
        for vector in vectors:
            actual = transform_srgb(vector['rgb'], normalize_material_settings(vector['settings']))
            for got, expected in zip(actual, vector['expected']):
                self.assertAlmostEqual(got, expected, places=4)

    def test_bounds(self):
        value = normalize_material_settings({'brightness': 9, 'metallic': -1})
        self.assertEqual(value['brightness'], 1.5)
        self.assertEqual(value['metallic'], 0)
```

- [ ] **Step 6: Run Python test and verify RED**

Run: `engine/venv/bin/python -m unittest engine/test_material_settings.py -v`

Expected: FAIL importing `engine.material_settings`.

- [ ] **Step 7: Implement Python parity and verify both runtimes**

Implement the same defaults, bounds, `#RRGGBB` parser, Rec.709 luminance, ordered transform, and clamp in `engine/material_settings.py` without Pillow or NumPy dependencies.

Run:

```bash
node --test src/lib/materialSettings.test.js
engine/venv/bin/python -m unittest engine/test_material_settings.py -v
```

Expected: both commands exit 0.

- [ ] **Step 8: Register test scripts and commit**

Add:

```json
"test:unit": "node --test electron/*.test.js src/lib/*.test.js engine/*.test.js",
"test:engine": "engine/venv/bin/python -m unittest discover -s engine -p 'test_*.py' -v"
```

Commit:

```bash
git add shared/material-color-vectors.json src/lib/materialSettings.js src/lib/materialSettings.test.js engine/material_settings.py engine/test_material_settings.py package.json
git commit -m "feat(material): define shared PBR adjustment contract"
```

---

### Task 2: PBR gate and exact GLB materialization

**Files:**
- Create: `engine/pbr_glb.py`
- Create: `engine/test_pbr_glb.py`

**Interfaces:**
- Consumes: `transform_srgb(rgb, settings)` and `normalize_material_settings(settings)`.
- Produces: `inspect_pbr_glb(path, expected_size) -> dict`.
- Produces: `materialize_pbr_glb(source, destination, settings) -> dict`.
- A passing report contains `passed`, `uv`, `base_color`, `metallic_roughness`, `texture_size`, and `reasons`.

- [ ] **Step 1: Write a synthetic GLB fixture helper and failing gate tests**

Use `pygltflib` to build one triangle with POSITION and TEXCOORD_0 accessors, a 2×2 embedded PNG, a `PbrMetallicRoughness` material, and embedded base-color/MR images. Test four variants:

The test helper `read_base_color_pixel(gltf, x, y)` converts embedded images to data URIs, decodes the material's `baseColorTexture` with Pillow, and returns one RGBA tuple. It is test-only and never enters runtime code.

```python
class PbrGlbTests(unittest.TestCase):
    def test_accepts_complete_pbr_glb(self):
        path = self.make_glb(uv=True, base=True, mr=True, size=2)
        report = inspect_pbr_glb(path, expected_size=2)
        self.assertTrue(report['passed'], report['reasons'])

    def test_rejects_missing_uv(self):
        report = inspect_pbr_glb(self.make_glb(uv=False), expected_size=2)
        self.assertIn('missing_texcoord_0', report['reasons'])

    def test_rejects_missing_metallic_roughness(self):
        report = inspect_pbr_glb(self.make_glb(mr=False), expected_size=2)
        self.assertIn('missing_metallic_roughness_texture', report['reasons'])

    def test_rejects_wrong_atlas_size(self):
        report = inspect_pbr_glb(self.make_glb(size=2), expected_size=4)
        self.assertIn('unexpected_texture_size', report['reasons'])
```

- [ ] **Step 2: Run gate tests and verify RED**

Run: `engine/venv/bin/python -m unittest engine/test_pbr_glb.PbrGlbTests -v`

Expected: FAIL importing `engine.pbr_glb`.

- [ ] **Step 3: Implement structural PBR inspection**

Core behavior:

```python
def inspect_pbr_glb(path, expected_size):
    gltf = GLTF2().load_binary(str(path))
    reasons = []
    primitives = [primitive for mesh in gltf.meshes for primitive in mesh.primitives]
    if not primitives or any(getattr(p.attributes, 'TEXCOORD_0', None) is None for p in primitives):
        reasons.append('missing_texcoord_0')
    materials = [gltf.materials[p.material] for p in primitives if p.material is not None]
    if not materials or any(m.pbrMetallicRoughness.baseColorTexture is None for m in materials):
        reasons.append('missing_base_color_texture')
    if not materials or any(m.pbrMetallicRoughness.metallicRoughnessTexture is None for m in materials):
        reasons.append('missing_metallic_roughness_texture')
    # Decode referenced images, verify non-empty pixels and exact expected_size.
    return {'passed': not reasons, 'reasons': reasons, 'texture_size': expected_size if not reasons else None}
```

Also validate accessor counts, finite UV floats, bufferView ranges, non-empty alpha/color range, and finite mesh AABB before `passed=True`.

- [ ] **Step 4: Run gate tests and verify GREEN**

Run: `engine/venv/bin/python -m unittest engine/test_pbr_glb.PbrGlbTests -v`

Expected: 4 tests, 0 failures.

- [ ] **Step 5: Add failing materialization test**

```python
def test_materializes_color_and_pbr_factors_without_mutating_source(self):
    source = self.make_glb(size=2, pixel=(51, 102, 153, 255))
    before = sha256(Path(source).read_bytes()).hexdigest()
    destination = Path(self.temp.name) / 'delivery.glb'
    report = materialize_pbr_glb(source, destination, {
        'brightness': 1.1, 'contrast': 1.2, 'saturation': 0.8,
        'tint': '#ff8000', 'tintStrength': 0.25,
        'roughness': 0.22, 'metallic': 0.75,
    })
    self.assertTrue(report['passed'])
    self.assertEqual(before, sha256(Path(source).read_bytes()).hexdigest())
    exported = GLTF2().load_binary(str(destination))
    pbr = exported.materials[0].pbrMetallicRoughness
    self.assertEqual(pbr.roughnessFactor, 0.22)
    self.assertEqual(pbr.metallicFactor, 0.75)
    self.assertEqual(read_base_color_pixel(exported, 0, 0), (104, 112, 121, 255))
```

- [ ] **Step 6: Implement lossless GLB image replacement**

Implementation sequence:

```python
gltf = GLTF2().load_binary(str(source))
gltf.convert_images(ImageFormat.DATAURI)
# For each referenced baseColor image: decode data URI, transform RGB pixels,
# preserve alpha and MIME type, then replace image.uri with a new data URI.
for material in gltf.materials:
    pbr = material.pbrMetallicRoughness
    pbr.roughnessFactor = settings['roughness']
    pbr.metallicFactor = settings['metallic']
gltf.convert_images(ImageFormat.BUFFERVIEW)
gltf.save_binary(str(destination))
report = inspect_pbr_glb(destination, expected_size=source_size)
if not report['passed']:
    Path(destination).unlink(missing_ok=True)
    raise ValueError('; '.join(report['reasons']))
```

- [ ] **Step 7: Verify materialization and commit**

Run: `npm run test:engine`

Expected: all Python tests pass.

Commit:

```bash
git add engine/pbr_glb.py engine/test_pbr_glb.py
git commit -m "feat(engine): validate and materialize PBR GLB"
```

---

### Task 3: MLX Paint provider and real profile mapping

**Files:**
- Create: `engine/paint_service.py`
- Create: `engine/test_paint_service.py`

**Interfaces:**
- Produces: `PAINT_PROFILES` exact config table.
- Produces: `build_paint_config(profile_id)`.
- Produces: `PaintService.run(source_glb, reference_png, output_glb, profile_id, cancelled, progress) -> dict`.
- `progress(percent, stage)` is synchronous; `cancelled()` returns bool.

- [ ] **Step 1: Write failing profile tests**

```python
class PaintProfileTests(unittest.TestCase):
    def test_profiles_map_to_real_cost_controls(self):
        expected = {
            'fast': (4, 256, 10, 1024, False),
            'balanced': (6, 512, 15, 1024, False),
            'quality': (6, 512, 15, 2048, True),
        }
        for name, values in expected.items():
            cfg = build_paint_config(name)
            actual = (cfg.max_selected_view_num, cfg.resolution, cfg.mlx_num_inference_steps, cfg.texture_size, cfg.use_mlx_super_res)
            self.assertEqual(actual, values)

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'texture profile'):
            build_paint_config('ultra')
```

- [ ] **Step 2: Run and verify RED**

Run: `engine/venv/bin/python -m unittest engine/test_paint_service.py -v`

Expected: FAIL importing `engine.paint_service`.

- [ ] **Step 3: Implement profile construction and lazy imports**

```python
PAINT_PROFILES = {
    'fast': {'views': 4, 'resolution': 256, 'steps': 10, 'texture_size': 1024, 'super_res': False},
    'balanced': {'views': 6, 'resolution': 512, 'steps': 15, 'texture_size': 1024, 'super_res': False},
    'quality': {'views': 6, 'resolution': 512, 'steps': 15, 'texture_size': 2048, 'super_res': True},
}

def build_paint_config(profile_id):
    value = PAINT_PROFILES.get(profile_id)
    if value is None:
        raise ValueError(f'Unknown texture profile: {profile_id}')
    from textureGenPipeline_mlx import Hunyuan3DPaintConfigMLX
    cfg = Hunyuan3DPaintConfigMLX(value['views'], value['resolution'])
    cfg.mlx_num_inference_steps = value['steps']
    cfg.texture_size = value['texture_size']
    cfg.render_size = value['texture_size']
    cfg.use_mlx_super_res = value['super_res']
    return cfg
```

At module load, resolve `SOURCE = Path(__file__).parent / 'Hunyuan3D-2.1-mlx' / 'hy3dpaint'` and prepend it to `sys.path` only when present. Do not import Paint/MLX modules until `build_paint_config` or the default pipeline factory is called.

- [ ] **Step 4: Add fake-pipeline lifecycle tests**

Inject `pipeline_factory` into `PaintService`. The fake records config, copies a valid synthetic PBR GLB to the requested output, and proves:

- progress reports loading, generation/bake, validation, ready in monotonic order;
- cancellation before pipeline call raises `PaintCancelled`;
- provider exception is returned as failed and does not modify source;
- output passes `inspect_pbr_glb` using the profile atlas size.

- [ ] **Step 5: Implement minimal lifecycle and verify GREEN**

`PaintService.run` must:

1. SHA-256 source before work;
2. construct config and pipeline lazily;
3. call pipeline with `use_remesh=True`, `save_glb=True`;
4. move generated `textured.glb` to unique output;
5. gate output;
6. compare source SHA-256 unchanged;
7. clear pipeline references, `gc.collect()`, and `mlx.core.clear_cache()` in `finally`.

Run: `npm run test:engine`

Expected: all Python tests pass without downloading weights.

- [ ] **Step 6: Commit**

```bash
git add engine/paint_service.py engine/test_paint_service.py
git commit -m "feat(engine): add profiled MLX Paint service"
```

---

### Task 4: Async texture jobs and durable reference artifacts

**Files:**
- Modify: `engine/server.py`
- Create: `engine/test_server_texture.py`

**Interfaces:**
- Produces HTTP `POST /texture`, `GET /status/{job_id}`, `POST /cancel/{job_id}`.
- Produces HTTP `POST /materialize`.
- Shape result adds `reference_path` and keeps the prepared reference after success.
- Texture result adds `glb_path`, `parent_glb_path`, `report_path`, `texture_applied`, `profile`, `elapsed`.

- [ ] **Step 1: Write failing endpoint tests with FastAPI TestClient and fake PaintService**

```python
def test_texture_job_returns_only_after_pbr_gate(client, shape_glb, reference_png, fake_paint):
    started = client.post('/texture', json={
        'source_glb_path': str(shape_glb),
        'reference_path': str(reference_png),
        'profile': 'fast',
    })
    job_id = started.json()['job_id']
    result = wait_terminal(client, job_id)
    assert result['status'] == 'done'
    assert result['pbr_structural_valid'] is True
    assert result['parent_glb_path'] == str(shape_glb)

def test_cancelled_texture_keeps_shape(client, shape_glb, reference_png, blocking_paint):
    before = sha256(shape_glb.read_bytes()).hexdigest()
    job_id = client.post('/texture', json={
        'source_glb_path': str(shape_glb),
        'reference_path': str(reference_png),
        'profile': 'fast',
    }).json()['job_id']
    client.post(f'/cancel/{job_id}')
    assert wait_terminal(client, job_id)['status'] == 'cancelled'
    assert sha256(shape_glb.read_bytes()).hexdigest() == before
```

- [ ] **Step 2: Run endpoint tests and verify RED**

Run: `engine/venv/bin/python -m unittest engine/test_server_texture.py -v`

Expected: `/texture` returns 404 or test import fails for missing request types.

- [ ] **Step 3: Preserve the prepared reference on successful Shape**

Change Shape cleanup semantics:

```python
prepared_path = JOBS_DIR / f'{job_id}-reference.png'
# Success result includes reference_path. cleanup_job removes raw upload always,
# but removes reference only on error/cancel before a reusable Shape exists.
```

The Shape report and Electron response must not claim texture even if the old `texture` request field is true; Stage 2 is separate.

- [ ] **Step 4: Implement texture job models and runner**

```python
class TextureRequest(BaseModel):
    source_glb_path: str
    reference_path: str
    profile: Literal['fast', 'balanced', 'quality'] = 'balanced'

class MaterializeRequest(BaseModel):
    paint_glb_path: str
    settings: dict

paint_service = PaintService()

def run_texture_job(job_id, request):
    job = jobs[job_id]
    output = JOBS_DIR / f'{job_id}-paint.glb'
    result = paint_service.run(
        source_glb=Path(request.source_glb_path),
        reference_png=Path(request.reference_path),
        output_glb=output,
        profile_id=request.profile,
        cancelled=lambda: bool(job.get('cancel_requested')),
        progress=lambda percent, stage: job.update(progress=percent, stage=stage),
    )
    if job.get('cancel_requested'):
        mark_cancelled(job_id)
        output.unlink(missing_ok=True)
        return
    job.update(status='done', progress=100, stage='Validación estructural lista', glb_path=str(output), pbr_structural_valid=True, **result)
```

Validate resolved source/reference paths exist and are inside `JOBS_DIR`; reject traversal with HTTP 400.

- [ ] **Step 5: Implement `/materialize` and verify tests**

Materialize to `JOBS_DIR/<uuid>-delivery.glb`, normalize settings, call `materialize_pbr_glb`, save a report, and return `{ok, glb_path, report_path}`.

Run: `npm run test:engine`

Expected: all Python tests pass; fake Paint never loads MLX weights.

- [ ] **Step 6: Commit**

```bash
git add engine/server.py engine/test_server_texture.py
git commit -m "feat(engine): expose cancellable texture jobs"
```

---

### Task 5: Owner-scoped artifact registry and ID-only Electron IPC

**Files:**
- Create: `electron/artifact-registry.js`
- Create: `electron/artifact-registry.test.js`
- Modify: `electron/main.js`
- Modify: `electron/preload.js`

**Interfaces:**
- Produces: `createArtifactRegistry({ allowedRoots })`.
- Registry methods: `register({ ownerId, path, kind, parentId })`, `resolve({ ownerId, artifactId, kinds })`, `rehydrate({ ownerId, entries })`, `clearOwner(ownerId)`.
- Preload adds `texture3D`, `cancelTexture`, `onTextureProgress`, `exportVisibleGlb`, `readGlbArtifact`.

- [ ] **Step 1: Write failing registry tests**

```js
test('resolves an artifact only for its owner and allowed kind', () => {
  const registry = createArtifactRegistry({ allowedRoots: [tempDir] });
  const artifact = registry.register({ ownerId: 7, path: glbPath, kind: 'shape' });
  assert.equal(registry.resolve({ ownerId: 7, artifactId: artifact.id, kinds: ['shape'] }).path, glbPath);
  assert.throws(() => registry.resolve({ ownerId: 8, artifactId: artifact.id, kinds: ['shape'] }), /owner/);
  assert.throws(() => registry.resolve({ ownerId: 7, artifactId: artifact.id, kinds: ['paint'] }), /kind/);
});

test('rejects a path outside allowed roots', () => {
  assert.throws(() => registry.register({ ownerId: 7, path: '/etc/passwd', kind: 'shape' }), /allowed root/);
});
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test electron/artifact-registry.test.js`

Expected: FAIL importing `artifact-registry.js`.

- [ ] **Step 3: Implement registry and verify GREEN**

Use `crypto.randomUUID()`, `path.resolve()`, separator-aware root containment, `fs.realpathSync`, extension allowlists (`.glb`, `.png`), and owner/kind checks. Never return paths to renderer from `resolve`.

Run: `node --test electron/artifact-registry.test.js`

Expected: all registry tests pass.

- [ ] **Step 4: Register Shape/reference results and rehydrate history**

When Shape finishes:

```js
const shape = artifactRegistry.register({ ownerId: event.sender.id, path: js.glb_path, kind: 'shape' });
const reference = artifactRegistry.register({ ownerId: event.sender.id, path: js.reference_path, kind: 'reference' });
return {
  ok: true,
  artifactId: shape.id,
  referenceArtifactId: reference.id,
  glbBase64: buf.toString('base64'),
  faces: js.faces,
  duration: js.elapsed,
  qualityLevel: js.quality_level,
  qualityScore: js.quality_score,
  qualityText: js.quality_text,
};
```

`ollama:loadHistory` validates stored paths, registers existing Shape/Paint/reference files, and returns ephemeral IDs. Missing files become `textureStatus: 'unavailable'`; they do not delete history.

- [ ] **Step 5: Add texture polling IPC**

`hunyuan:texture3D` accepts only `{ sourceArtifactId, referenceArtifactId, profile }`, resolves owner artifacts, calls `/texture`, polls status, emits `hunyuan:texture-progress`, registers the Paint output, reads base64, and returns `{ paintArtifactId, paintGlbBase64, gateReportPath, pbrStructuralValid }`. It must not return `textureApplied=true`; final readiness also requires the neutral render check in Task 6.

Maintain a separate `hunyuanActiveTextureJobId` so cancelling Paint never cancels Shape/STL accidentally.

- [ ] **Step 6: Add ID-only visible export**

`hunyuan:exportVisibleGlb` accepts:

```js
{ shapeArtifactId, paintArtifactId, textureEnabled, settings, filename }
```

If disabled, copy resolved Shape. If enabled, resolve Paint, call `/materialize`, validate response, and copy Delivery to `STL_SAVE_DIR`. Sanitize filename with `path.basename` and force `.glb`.

- [ ] **Step 7: Expose preload surface and commit**

```js
texture3D: (params) => ipcRenderer.invoke('hunyuan:texture3D', params),
cancelTexture: () => ipcRenderer.invoke('hunyuan:cancelTexture'),
onTextureProgress: (callback) => { /* subscribe and return unsubscribe */ },
exportVisibleGlb: (params) => ipcRenderer.invoke('hunyuan:exportVisibleGlb', params),
readGlbArtifact: (artifactId) => ipcRenderer.invoke('hunyuan:readGlbArtifact', { artifactId }),
```

Run: `npm run test:unit`

Expected: all Node tests pass.

Commit:

```bash
git add electron/artifact-registry.js electron/artifact-registry.test.js electron/main.js electron/preload.js
git commit -m "feat(electron): add owned PBR artifact workflow"
```

---

### Task 6: Reversible Three.js material preview

**Files:**
- Create: `src/lib/materialPreview.js`
- Create: `src/lib/materialPreview.test.js`
- Modify: `src/components/GltfViewer.jsx`

**Interfaces:**
- Consumes normalized `MaterialSettings`.
- Produces: `snapshotSceneMaterials(scene)`, `applyPreviewSettings(scene, settings)`, `restoreSceneMaterials(scene)`, `setTextureSceneVisibility({ shapeScene, paintScene, enabled, compareOriginal })`.
- `GltfViewer` props become `{ shapeGlbBase64, paintGlbBase64, textureEnabled, compareOriginal, materialSettings, onPaintRenderValidated }`.

- [ ] **Step 1: Write failing material snapshot and visibility tests**

```js
test('restores original PBR factors after preview edits', () => {
  const material = new THREE.MeshStandardMaterial({ roughness: 0.63, metalness: 0.08 });
  const scene = new THREE.Scene();
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(), material));
  snapshotSceneMaterials(scene);
  applyPreviewSettings(scene, { ...DEFAULT_MATERIAL_SETTINGS, roughness: 0.2, metallic: 0.9 });
  assert.equal(material.roughness, 0.2);
  assert.equal(material.metalness, 0.9);
  restoreSceneMaterials(scene);
  assert.equal(material.roughness, 0.63);
  assert.equal(material.metalness, 0.08);
});

test('compare original overrides the texture switch', () => {
  const shapeScene = { visible: false }, paintScene = { visible: false };
  setTextureSceneVisibility({ shapeScene, paintScene, enabled: true, compareOriginal: true });
  assert.equal(shapeScene.visible, true);
  assert.equal(paintScene.visible, false);
});
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test src/lib/materialPreview.test.js`

Expected: FAIL importing `materialPreview.js`.

- [ ] **Step 3: Implement snapshots, factor overrides, and shader contract**

Store original roughness, metalness, `onBeforeCompile`, and `customProgramCacheKey` in a `WeakMap`. Patch standard materials so the fragment shader converts sampled base color linear→sRGB, applies the exact shared ordered formula using uniforms, then converts sRGB→linear. Update uniform values without replacing materials.

`customProgramCacheKey` must return a stable `xreality-material-preview-v1` key so Three recompiles once, not per slider move.

- [ ] **Step 4: Verify helper tests GREEN**

Run: `node --test src/lib/materialPreview.test.js`

Expected: all preview tests pass.

- [ ] **Step 5: Refactor GltfViewer to load and align two scenes**

Keep one renderer/camera/control loop. Parse Shape first and derive one canonical center/scale from the Shape AABB; apply that identical transform to Shape and Paint so remesh drift remains visible during comparison. Add both scenes once and toggle `.visible`; never reparse on slider changes. Dispose geometries, materials, textures, controls, renderer, ResizeObserver, and RAF on unmount.

After Paint parses, render it offscreen from front, rear, and grazing cameras under fixed neutral lights. Read pixels from a 256×256 `WebGLRenderTarget`; require non-background coverage and non-zero color variance in all three views. Call `onPaintRenderValidated({ passed, reasons })` once. This is the render portion of `generated_textured_pbr`; App may set `textureApplied=true` only when both `pbrStructuralValid` and this callback pass.

- [ ] **Step 6: Build and commit**

Run: `npm run build:vite`

Expected: Vite exits 0 with no unresolved imports.

Commit:

```bash
git add src/lib/materialPreview.js src/lib/materialPreview.test.js src/components/GltfViewer.jsx
git commit -m "feat(viewer): preview reversible PBR adjustments"
```

---

### Task 7: Material overlay and deterministic editor state

**Files:**
- Create: `src/lib/materialEditorState.js`
- Create: `src/lib/materialEditorState.test.js`
- Create: `src/components/MaterialOverlay.jsx`
- Modify: `src/index.css`

**Interfaces:**
- Produces: `createMaterialEditorState(persisted?)` and `materialEditorReducer(state, action)`.
- `MaterialOverlay` receives state, `dispatch`, `onGenerate`, `onCancel`, `onExport`, `onCompareStart`, `onCompareEnd`, and `disabledReason`.

- [ ] **Step 1: Write failing reducer tests**

```js
test('slider edits change preset to custom without starting Paint', () => {
  const initial = createMaterialEditorState();
  const next = materialEditorReducer(initial, { type: 'settings/change', key: 'roughness', value: 0.2 });
  assert.equal(next.appearancePreset, 'custom');
  assert.equal(next.settings.roughness, 0.2);
  assert.equal(next.textureStatus, 'none');
});

test('failed Paint preserves the last ready variant', () => {
  const ready = { ...createMaterialEditorState(), textureStatus: 'ready', paintArtifactId: 'paint-1' };
  const failed = materialEditorReducer(ready, { type: 'paint/failed', error: 'OOM' });
  assert.equal(failed.paintArtifactId, 'paint-1');
  assert.equal(failed.error, 'OOM');
});
```

- [ ] **Step 2: Run and verify RED**

Run: `node --test src/lib/materialEditorState.test.js`

Expected: FAIL importing reducer.

- [ ] **Step 3: Implement reducer and verify GREEN**

Actions: `overlay/toggle`, `texture/toggle`, `profile/select`, `preset/select`, `settings/change`, `settings/reset`, `compare/start`, `compare/end`, `paint/queued`, `paint/progress`, `paint/structural-valid`, `paint/render-valid`, `paint/ready`, `paint/failed`, `paint/cancelled`, `export/start`, `export/done`, `export/failed`. `settings/reset` restores factors captured from the current Paint material, not hard-coded defaults.

Run: `node --test src/lib/materialEditorState.test.js`

Expected: all reducer tests pass.

- [ ] **Step 4: Build the approved overlay**

Implement:

- top-right absolute positioning inside the GLB viewport;
- expanded/collapsed states from approved mockup C;
- stable non-draggable placement;
- labeled switch and profile buttons;
- Generate/Regenerate or Cancel based on lifecycle;
- Natural/Matte/Glossy/Metallic presets plus Custom state;
- range inputs for brightness, contrast, saturation, tint strength, roughness, metallic and a color input for tint;
- press/keyboard-safe `Ver original` using pointer/key down/up and blur cleanup;
- `Exportar GLB visible`;
- visible error and progress stage;
- `aria-*`, focus rings, disabled reason, reduced-motion styles.

- [ ] **Step 5: Build and commit**

Run:

```bash
npm run test:unit
npm run build:vite
```

Expected: both exit 0.

Commit:

```bash
git add src/lib/materialEditorState.js src/lib/materialEditorState.test.js src/components/MaterialOverlay.jsx src/index.css
git commit -m "feat(ui): add realtime material overlay"
```

---

### Task 8: End-to-end React workflow, history, and visible export

**Files:**
- Modify: `src/App.jsx`
- Modify: `src/components/ImageViewer.jsx`

**Interfaces:**
- Consumes new preload APIs from Task 5 and viewer/overlay APIs from Tasks 6–7.
- GLB history entries persist `glbPath`, `referencePath`, `paintGlbPath`, `textureProfile`, `textureStatus`, `textureEnabled`, `materialSettings`, `gateReportPath`; ephemeral artifact IDs are returned by main on load.

- [ ] **Step 1: Add failing pure history tests**

Extract and export from `materialEditorState.js`:

```js
serializeMaterialState(state) -> persisted fields only
hydrateMaterialState(entry) -> normalized editor state
```

Test that base64, progress, transient errors, and ephemeral IDs are not serialized, while settings/profile/switch are restored.

- [ ] **Step 2: Run and verify RED, then implement serialization**

Run: `node --test src/lib/materialEditorState.test.js`

Expected RED: missing exports. Implement minimal serializers; rerun and expect GREEN.

- [ ] **Step 3: Integrate texture lifecycle in App**

After Shape success, store `artifactId`, `referenceArtifactId`, `glbPath`, `referencePath`. Add:

```js
handleGenerateTexture()
handleCancelTexture()
handleExportVisibleGlb()
```

`handleGenerateTexture` calls `window.hunyuan.texture3D` with IDs and profile, then attaches Paint ID/base64/report without replacing Shape base64. Progress subscription filters by active job ID. It dispatches structural validity first, waits for `GltfViewer.onPaintRenderValidated`, and dispatches `paint/ready` only when both gates pass. A failed regeneration retains the previous ready Paint.

- [ ] **Step 4: Integrate overlay and dual-scene viewer in ImageViewer**

Place `MaterialOverlay` inside the GLB viewport wrapper, above `GltfViewer`. Pass Shape and Paint base64 separately. Keep the existing metadata/audit area and STL export. Rename the existing GLB save action to `Exportar GLB visible` for GLB results and route it through the new handler.

- [ ] **Step 5: Integrate gallery recovery**

When selecting a history GLB, read Shape and Paint by artifact IDs returned from main. If Paint is missing, show Shape and `PBR no disponible`; never show a blank viewer. Persist updated settings after each reducer change with debounce, excluding blobs.

- [ ] **Step 6: Verify unit/build and commit**

Run:

```bash
npm run test:unit
npm run test:engine
npm run build:vite
```

Expected: all commands exit 0.

Commit:

```bash
git add src/App.jsx src/components/ImageViewer.jsx src/lib/materialEditorState.js src/lib/materialEditorState.test.js
git commit -m "feat: integrate non-destructive PBR texture workflow"
```

---

### Task 9: Packaging, documentation, browser QA, and real MLX smoke

**Files:**
- Modify: `package.json`
- Modify: `electron/main.js`
- Modify: `engine/setup.sh`
- Modify: `docs/MANUAL.md`
- Test: all files from Tasks 1–8

**Interfaces:**
- Packaged app contains `server.py`, `material_settings.py`, `pbr_glb.py`, `paint_service.py`, and `setup.sh` under unpacked engine resources.
- Installed engine marker increments from `4` to `5` only after new files copy successfully.

- [ ] **Step 1: Add failing package-content assertion**

Extend `engine/setup.test.js` or add a Node test that reads `package.json` and asserts every runtime Python module is included in both `build.files` and `build.asarUnpack`.

Run: `node --test engine/setup.test.js`

Expected: FAIL because only `engine/server.py` and `engine/setup.sh` are packaged.

- [ ] **Step 2: Package and install runtime modules**

Change package entries to explicit runtime files:

```json
"asarUnpack": [
  "engine/server.py",
  "engine/material_settings.py",
  "engine/pbr_glb.py",
  "engine/paint_service.py",
  "engine/setup.sh"
],
"files": [
  "build/**/*",
  "electron/**/*",
  "engine/server.py",
  "engine/material_settings.py",
  "engine/pbr_glb.py",
  "engine/paint_service.py",
  "engine/setup.sh",
  "dist/**/*"
]
```

Change `prepareHunyuanEngineFiles()` to copy `server.py`, `material_settings.py`, `pbr_glb.py`, `paint_service.py`, and `setup.sh`. Set both Electron `HUNYUAN_INSTALL_VERSION` and setup marker to `5`.

- [ ] **Step 3: Update manual**

Document:

- Paint is optional and preserves original;
- profile costs and Balanceado default;
- switch/export semantics;
- every live control;
- OOM recovery by explicit lower profile;
- first Paint weight loading;
- Hunyuan license/territory notice already applicable to the engine.

- [ ] **Step 4: Run complete automated verification**

```bash
npm run test:unit
npm run test:engine
npm run test:tools
npm run build:vite
git diff --check
```

Expected: all exit 0, no failed tests, no whitespace errors.

- [ ] **Step 5: Browser verification**

Launch `npm run dev`, open `http://localhost:5173`, generate or load a Shape, and verify:

1. overlay C is top-right and collapses;
2. keyboard can reach switch, profiles, presets, controls, compare, export;
3. switch toggles Shape/Paint without a network/IPC Paint call;
4. every slider changes the preview and Custom state;
5. `Ver original` restores Paint on pointer/key release and blur;
6. narrow window keeps controls reachable and does not cover export permanently;
7. reduced motion removes nonessential animation.

Capture screenshots of expanded, collapsed, original, and PBR states under `docs/evidence/pbr-editor/` only if the repository's evidence policy expects tracked screenshots; otherwise report paths outside Git.

- [ ] **Step 6: Run real `fast` Paint smoke with the dog reference**

Use the current dog Shape/reference artifacts through the app, not a mock. Record:

- source SHA-256 before and after;
- profile/config values;
- duration and peak memory observed;
- Paint GLB path/digest;
- gate report with UV, albedo, MR, atlas 1024;
- exported Delivery digest;
- reload screenshot under fixed camera/light.

If the current dog reference is unavailable, regenerate Shape from the attached dog image first. If MLX Paint fails, preserve full error and logs capped to the last 5 KB; do not mark the feature complete.

- [ ] **Step 7: Build and validate packaged app**

```bash
npm run build
codesign --verify --deep --strict --verbose=2 "release/mac-arm64/Xreality Convert.app"
open "release/mac-arm64/Xreality Convert.app"
```

Inside the packaged app, verify the engine preflight, load the dog Shape/Paint history, toggle material, change roughness, and export a reloadable GLB. Notarization remains a separate credential-dependent release step.

- [ ] **Step 8: Final commit**

```bash
git add package.json electron/main.js engine/setup.sh docs/MANUAL.md
git commit -m "build: ship local PBR texture workflow"
```

Run `git status --short`; expected output is empty.

---

## Final Acceptance Evidence

- Original GLB SHA-256 unchanged.
- Fast Paint produces a structurally valid 1K PBR GLB with UV, base color, and metallic-roughness.
- Switch and sliders require no additional Paint inference.
- Export with texture off reloads as Shape; export with texture on reloads as adjusted PBR.
- Previous ready Paint survives failed/cancelled regeneration.
- History reload restores settings or degrades visibly to Shape when Paint is missing.
- Node, Python, Vite, browser, real MLX, packaged-app, codesign, and Git-clean evidence are fresh.
