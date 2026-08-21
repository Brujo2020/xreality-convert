import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  Camera,
  Cube,
  Eye,
  Lightbulb,
  CornersOut,
  CornersIn,
  PaintBrush,
  Pause,
  Play,
  Polygon,
  ArrowsOutCardinal,
  ArrowsInLineHorizontal,
  ArrowsClockwise,
  DownloadSimple,
  WarningOctagon,
  Sparkle,
} from '@phosphor-icons/react';
import { sounds } from '../lib/soundEffects.js';

function base64ToArrayBuffer(base64) {
  if (!base64 || typeof base64 !== 'string') return new ArrayBuffer(0);
  try {
    const clean = base64.includes(',') ? base64.split(',')[1] : base64;
    const sanitized = clean.replace(/\s/g, '');
    const binary = atob(sanitized);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return bytes.buffer;
  } catch (err) {
    console.error('Failed to parse base64 buffer:', err);
    return new ArrayBuffer(0);
  }
}

function localFileUrl(filePath) {
  return `file://${String(filePath).split('/').map((part) => encodeURIComponent(part)).join('/')}`;
}

function disposeObject(root) {
  if (!root) return;
  root.traverse((object) => {
    object.geometry?.dispose?.();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.filter(Boolean).forEach((material) => {
      Object.values(material).forEach((value) => {
        if (value?.isTexture) value.dispose();
      });
      material.dispose?.();
    });
  });
}

// Generate high-contrast procedural UV checker texture
function createUvCheckerTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d');
  const size = 32;
  for (let x = 0; x < canvas.width; x += size) {
    for (let y = 0; y < canvas.height; y += size) {
      const isEven = (x / size + y / size) % 2 === 0;
      ctx.fillStyle = isEven ? '#38bdf8' : '#03102b';
      ctx.fillRect(x, y, size, size);
      // Small grid border
      ctx.strokeStyle = 'rgba(255,255,255,0.15)';
      ctx.strokeRect(x, y, size, size);
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(4, 4);
  return texture;
}

export default function GltfViewer({
  glbBase64,
  glbPath,
  externalAction,
  onClearExternalAction,
}) {
  const mountRef = useRef(null);
  const [error, setError] = useState(null);

  // Studio Controls State
  const [shadingMode, setShadingMode] = useState('lit'); // 'lit' | 'wireframe' | 'clay' | 'uv_checker' | 'normals' | 'xray'
  const [lightingPreset, setLightingPreset] = useState('studio'); // 'studio' | 'cyberpunk' | 'sunset' | 'scifi' | 'dark'
  const [turntable, setTurntable] = useState(true);
  const [turntableSpeed, setTurntableSpeed] = useState(1.2);
  const [showBbox, setShowBbox] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Mesh Statistics
  const [stats, setStats] = useState({
    triangles: 0,
    vertices: 0,
    meshes: 0,
    dimensions: { x: 0, y: 0, z: 0 },
  });

  // Scene references
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const modelRef = useRef(null);
  const originalMaterialsRef = useRef(new Map());
  const lightsGroupRef = useRef(null);
  const bboxHelperRef = useRef(null);
  const gridRef = useRef(null);
  const floorRef = useRef(null);
  const uvCheckerTextureRef = useRef(null);

  // Apply Shading Mode to Loaded Model
  const applyShading = useCallback((mode) => {
    if (!modelRef.current) return;
    const model = modelRef.current;

    if (!uvCheckerTextureRef.current) {
      uvCheckerTextureRef.current = createUvCheckerTexture();
    }

    model.traverse((object) => {
      if (object.isMesh) {
        if (!originalMaterialsRef.current.has(object.id)) {
          originalMaterialsRef.current.set(object.id, object.material);
        }
        const origMat = originalMaterialsRef.current.get(object.id);

        if (mode === 'lit') {
          object.material = origMat;
          object.material.wireframe = false;
        } else if (mode === 'wireframe') {
          object.material = new THREE.MeshStandardMaterial({
            color: 0x38bdf8,
            wireframe: true,
            roughness: 0.5,
            metalness: 0.2,
          });
        } else if (mode === 'clay') {
          object.material = new THREE.MeshStandardMaterial({
            color: 0xd6d3d1, // Warm clay
            roughness: 0.72,
            metalness: 0.05,
            flatShading: false,
          });
        } else if (mode === 'uv_checker') {
          object.material = new THREE.MeshStandardMaterial({
            map: uvCheckerTextureRef.current,
            roughness: 0.5,
            metalness: 0.1,
          });
        } else if (mode === 'normals') {
          object.material = new THREE.MeshNormalMaterial({
            flatShading: false,
          });
        } else if (mode === 'xray') {
          object.material = new THREE.MeshStandardMaterial({
            color: 0x06b6d4,
            transparent: true,
            opacity: 0.55,
            wireframe: false,
            roughness: 0.1,
            metalness: 0.9,
          });
        }
        if (object.material) object.material.needsUpdate = true;
      }
    });
  }, []);

  // Apply Lighting Preset to Scene
  const applyLighting = useCallback((preset) => {
    if (!lightsGroupRef.current || !sceneRef.current) return;
    const group = lightsGroupRef.current;
    while (group.children.length > 0) {
      group.remove(group.children[0]);
    }

    if (preset === 'studio') {
      sceneRef.current.background = new THREE.Color(0x030a16);
      group.add(new THREE.HemisphereLight(0xffffff, 0x1e293b, 1.2));
      const key = new THREE.DirectionalLight(0xffffff, 2.4);
      key.position.set(4, 6, 5);
      group.add(key);
      const fill = new THREE.DirectionalLight(0xfff6ee, 1.2);
      fill.position.set(-5, 2, 3);
      group.add(fill);
      const rim = new THREE.DirectionalLight(0xe2e8f0, 1.0);
      rim.position.set(1, 4, -5);
      group.add(rim);
    } else if (preset === 'cyberpunk') {
      sceneRef.current.background = new THREE.Color(0x020617);
      group.add(new THREE.HemisphereLight(0x06b6d4, 0x3b0764, 0.9));
      const cyanRim = new THREE.DirectionalLight(0x00f0ff, 3.2);
      cyanRim.position.set(5, 4, 3);
      group.add(cyanRim);
      const magentaRim = new THREE.DirectionalLight(0xff007f, 3.2);
      magentaRim.position.set(-5, 3, -4);
      group.add(magentaRim);
      const topFill = new THREE.DirectionalLight(0x38bdf8, 1.0);
      topFill.position.set(0, 6, 0);
      group.add(topFill);
    } else if (preset === 'sunset') {
      sceneRef.current.background = new THREE.Color(0x0c0a09);
      group.add(new THREE.HemisphereLight(0xfef08a, 0x1c1917, 1.1));
      const sun = new THREE.DirectionalLight(0xf97316, 3.0);
      sun.position.set(6, 2, 4);
      group.add(sun);
      const skyBounce = new THREE.DirectionalLight(0x38bdf8, 1.2);
      skyBounce.position.set(-4, 4, -3);
      group.add(skyBounce);
    } else if (preset === 'scifi') {
      sceneRef.current.background = new THREE.Color(0x00040f);
      group.add(new THREE.HemisphereLight(0x38bdf8, 0x020617, 0.7));
      const key = new THREE.DirectionalLight(0xe0f2fe, 3.5);
      key.position.set(2, 7, 3);
      group.add(key);
      const rim = new THREE.DirectionalLight(0x0284c7, 1.8);
      rim.position.set(-4, -2, -5);
      group.add(rim);
    } else if (preset === 'dark') {
      sceneRef.current.background = new THREE.Color(0x01040a);
      group.add(new THREE.HemisphereLight(0x94a3b8, 0x020617, 0.5));
      const subtleKey = new THREE.DirectionalLight(0xffffff, 1.6);
      subtleKey.position.set(0, 6, 4);
      group.add(subtleKey);
    }
  }, []);

  // Snap Camera to Canonical Angle
  const snapCamera = useCallback((view) => {
    if (!cameraRef.current || !controlsRef.current || !modelRef.current) return;
    const camera = cameraRef.current;
    const controls = controlsRef.current;

    const box = new THREE.Box3().setFromObject(modelRef.current);
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z) * 0.5 || 1;
    const dist = radius * 3.8;

    sounds.playSwitch();

    if (view === 'front') {
      camera.position.set(0, 0, dist);
    } else if (view === 'right') {
      camera.position.set(dist, 0, 0);
    } else if (view === 'back') {
      camera.position.set(0, 0, -dist);
    } else if (view === 'left') {
      camera.position.set(-dist, 0, 0);
    } else if (view === 'top') {
      camera.position.set(0, dist, 0.0001);
    } else if (view === 'bottom') {
      camera.position.set(0, -dist, 0.0001);
    } else if (view === 'iso') {
      camera.position.set(dist * 0.7, dist * 0.6, dist * 0.7);
    }
    camera.lookAt(0, 0, 0);
    controls.target.set(0, 0, 0);
    controls.update();
  }, []);

  // Take Instant High-Res 4K Transparent PNG Snapshot
  const captureSnapshot = useCallback(() => {
    if (!rendererRef.current || !sceneRef.current || !cameraRef.current) return;
    sounds.playSnapshot();

    const renderer = rendererRef.current;
    const scene = sceneRef.current;
    const camera = cameraRef.current;

    const origBg = scene.background;
    scene.background = null; // transparent background

    renderer.render(scene, camera);
    const dataUrl = renderer.domElement.toDataURL('image/png');

    scene.background = origBg;
    renderer.render(scene, camera);

    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `xreality-render-4k-${Date.now()}.png`;
    a.click();
  }, []);

  // External Action Handler (from Command Palette / Shortcuts)
  useEffect(() => {
    if (!externalAction) return;
    const { type, payload } = externalAction;
    if (type === 'shading') {
      setShadingMode(payload);
      applyShading(payload);
    } else if (type === 'lighting') {
      setLightingPreset(payload);
      applyLighting(payload);
    } else if (type === 'camera') {
      if (payload === 'toggle_turntable') {
        setTurntable((t) => !t);
      } else if (payload === 'snapshot') {
        captureSnapshot();
      } else {
        snapCamera(payload);
      }
    }
    if (onClearExternalAction) onClearExternalAction();
  }, [externalAction, applyShading, applyLighting, snapCamera, captureSnapshot, onClearExternalAction]);

  // Main Three.js Setup & GLTF Loading
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || (!glbPath && !glbBase64)) return undefined;

    setError(null);
    let animationFrame = null;
    let disposed = false;
    let fallbackTexture = null;
    let fallbackBitmap = null;
    const canonicalObjectUrls = [];
    const renderOnce = () => renderer.render(scene, camera);
    controls.addEventListener('change', renderOnce);

    try {
      const scene = new THREE.Scene();
      sceneRef.current = scene;
      scene.background = new THREE.Color(0x030a16);

      const camera = new THREE.PerspectiveCamera(38, mount.clientWidth / mount.clientHeight || 1, 0.01, 5000);
      cameraRef.current = camera;

      const renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        preserveDrawingBuffer: true,
        powerPreference: 'high-performance',
      });
      rendererRef.current = renderer;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2.0));
      renderer.setSize(mount.clientWidth || 400, mount.clientHeight || 400);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.15;
      mount.appendChild(renderer.domElement);

      const lightsGroup = new THREE.Group();
      lightsGroupRef.current = lightsGroup;
      scene.add(lightsGroup);
      applyLighting(lightingPreset);

      const controls = new OrbitControls(camera, renderer.domElement);
      controlsRef.current = controls;
      controls.enableDamping = true;
      controls.dampingFactor = 0.075;
      controls.autoRotate = turntable;
      controls.autoRotateSpeed = turntableSpeed;
      controls.minPolarAngle = 0.05;
      controls.maxPolarAngle = Math.PI * 0.95;

      const renderLoop = () => {
        if (disposed) return;
        controls.update();
        renderer.render(scene, camera);
        animationFrame = requestAnimationFrame(renderLoop);
      };

      const loader = new GLTFLoader();

      const onLoaded = (gltf) => {
        if (disposed) return;
        const model = gltf.scene;
        modelRef.current = model;

        let triCount = 0;
        let vertCount = 0;
        let meshCount = 0;

        model.traverse((object) => {
          if (object.isMesh) {
            meshCount += 1;
            if (object.geometry) {
              const geom = object.geometry;
              if (geom.index) {
                triCount += geom.index.count / 3;
              } else if (geom.attributes.position) {
                triCount += geom.attributes.position.count / 3;
              }
              if (geom.attributes.position) {
                vertCount += geom.attributes.position.count;
              }
            }

            const mats = Array.isArray(object.material) ? object.material : [object.material];
            mats.forEach((mat) => {
              if (!mat) return;
              if (mat.map) {
                mat.map.colorSpace = THREE.SRGBColorSpace;
                mat.map.needsUpdate = true;
              }
              if (!mat.map && (!mat.color || mat.color.getHex() === 0xffffff || mat.color.getHex() === 0x000000)) {
                mat.color = new THREE.Color(0x94a3b8);
                mat.roughness = 0.62;
                mat.metalness = 0.12;
              }
            });
          }
        });

        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        model.position.sub(center);
        scene.add(model);

        setStats({
          triangles: Math.round(triCount),
          vertices: Math.round(vertCount),
          meshes: meshCount,
          dimensions: {
            x: Math.round(size.x * 100) / 100,
            y: Math.round(size.y * 100) / 100,
            z: Math.round(size.z * 100) / 100,
          },
        });

        const radius = Math.max(size.x, size.y, size.z) * 0.5 || 1;
        const distance = radius * 4.4;
        camera.position.set(distance * 0.25, distance * 0.15, distance);
        camera.lookAt(0, 0, 0);
        camera.near = Math.max(radius / 100, 0.001);
        camera.far = radius * 100;
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.update();

        // Floor Shadow Catcher
        const floor = new THREE.Mesh(
          new THREE.CircleGeometry(radius * 3.4, 64),
          new THREE.MeshBasicMaterial({ color: 0x020817, transparent: true, opacity: 0.72 })
        );
        floorRef.current = floor;
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -radius * 1.02;
        scene.add(floor);

        // Floor Grid
        const grid = new THREE.GridHelper(radius * 5, 24, 0x1689e8, 0x0a2542);
        gridRef.current = grid;
        grid.position.y = -radius * 1.01;
        (Array.isArray(grid.material) ? grid.material : [grid.material]).forEach((m) => {
          m.opacity = 0.34;
          m.transparent = true;
        });
        scene.add(grid);

        // Bounding Box Helper
        const bboxHelper = new THREE.BoxHelper(model, 0x38bdf8);
        bboxHelper.visible = showBbox;
        bboxHelperRef.current = bboxHelper;
        scene.add(bboxHelper);

        applyShading(shadingMode);
        renderLoop();
      };

      const onLoadError = (err) => {
        console.error('Error loading GLTF model in viewer:', err);
        setError('Error al cargar la malla 3D.');
      };

      if (glbPath) {
        loader.load(localFileUrl(glbPath), onLoaded, undefined, (err) => {
          if (glbBase64) {
            const buf = base64ToArrayBuffer(glbBase64);
            if (buf.byteLength > 0) {
              loader.parse(buf, '', onLoaded, onLoadError);
              return;
            }
          }
          onLoadError(err);
        });
      } else if (glbBase64) {
        const buf = base64ToArrayBuffer(glbBase64);
        if (buf.byteLength > 0) {
          loader.parse(buf, '', onLoaded, onLoadError);
        } else {
          setError('Contenido base64 3D vacío.');
        }
      }

      const onResize = () => {
        if (disposed || !mount) return;
        const w = mount.clientWidth;
        const h = mount.clientHeight;
        if (w === 0 || h === 0) return;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      };

      window.addEventListener('resize', onResize);

      return () => {
        disposed = true;
        window.removeEventListener('resize', onResize);
        if (animationFrame) cancelAnimationFrame(animationFrame);
        if (controls) controls.dispose();
        if (renderer) {
          renderer.dispose();
          if (renderer.domElement && renderer.domElement.parentNode === mount) {
            mount.removeChild(renderer.domElement);
          }
        }
        disposeObject(scene);
      };
    } catch (err) {
      console.error('Three.js Init failed:', err);
      setError('No se pudo inicializar el motor WebGL.');
    }
  }, [glbBase64, glbPath]);

  // Update controls auto-rotation
  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = turntable;
      controlsRef.current.autoRotateSpeed = turntableSpeed;
    }
  }, [turntable, turntableSpeed]);

  // Update Bbox visibility
  useEffect(() => {
    if (bboxHelperRef.current) {
      bboxHelperRef.current.visible = showBbox;
    }
  }, [showBbox]);

  // Update Grid visibility
  useEffect(() => {
    if (gridRef.current) gridRef.current.visible = showGrid;
    if (floorRef.current) floorRef.current.visible = showGrid;
  }, [showGrid]);

  return (
    <div className={`relative h-full w-full select-none overflow-hidden ${isFullscreen ? 'fixed inset-0 z-50 bg-[#010714]' : ''}`}>
      {/* 3D Canvas Mount */}
      <div ref={mountRef} className="h-full w-full" />

      {error && (
        <div className="absolute inset-0 grid place-items-center bg-[#010714]/90 p-6 text-center backdrop-blur-md">
          <div className="max-w-sm rounded-3xl border border-rose-500/30 bg-rose-950/40 p-5 shadow-2xl">
            <WarningOctagon size={32} className="mx-auto text-rose-400 animate-pulse" weight="duotone" />
            <h3 className="mt-2 text-sm font-bold text-white font-outfit">Fallo en el visor 3D</h3>
            <p className="mt-1 text-xs text-rose-200/80">{error}</p>
          </div>
        </div>
      )}

      {/* Top Floating HUD: Shading & Lighting Modes */}
      <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-1.5 rounded-2xl border border-sky-400/25 bg-[#030d22]/85 p-1.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xl">
        {/* Shading modes */}
        <div className="flex items-center gap-1 border-r border-white/10 pr-1.5">
          {[
            { id: 'lit', label: 'PBR', icon: PaintBrush, title: 'Lit PBR Realista' },
            { id: 'wireframe', label: 'Wire', icon: Polygon, title: 'Wireframe Pro (W)' },
            { id: 'clay', label: 'Clay', icon: Eye, title: 'Clay MatCap (C)' },
            { id: 'uv_checker', label: 'UV', icon: Eye, title: 'UV Checker' },
            { id: 'normals', label: 'Norm', icon: Eye, title: 'Normales RGB' },
            { id: 'xray', label: 'X-Ray', icon: Sparkle, title: 'Holograma X-Ray' },
          ].map((mode) => (
            <button
              key={mode.id}
              onClick={() => {
                sounds.playClick();
                setShadingMode(mode.id);
                applyShading(mode.id);
              }}
              title={mode.title}
              className={`flex items-center gap-1 rounded-xl px-2.5 py-1 text-[10px] font-bold transition-all ${
                shadingMode === mode.id
                  ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-md border border-sky-300/40'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <mode.icon size={13} weight="duotone" />
              <span>{mode.label}</span>
            </button>
          ))}
        </div>

        {/* Lighting Environments */}
        <div className="flex items-center gap-1">
          {[
            { id: 'studio', label: 'Studio', title: 'Apple Studio Clean' },
            { id: 'cyberpunk', label: 'Neon', title: 'Cyberpunk Neon Synth' },
            { id: 'sunset', label: 'Sunset', title: 'Golden Hour Sunset' },
            { id: 'scifi', label: 'Sci-Fi', title: 'Deep Space Sci-Fi' },
          ].map((light) => (
            <button
              key={light.id}
              onClick={() => {
                sounds.playClick();
                setLightingPreset(light.id);
                applyLighting(light.id);
              }}
              title={light.title}
              className={`rounded-xl px-2 py-1 text-[10px] font-bold transition-all ${
                lightingPreset === light.id
                  ? 'bg-sky-500/25 border border-sky-400/40 text-cyan-200'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              {light.label}
            </button>
          ))}
        </div>
      </div>

      {/* Right Floating Tool Bar: Camera, Snapshots, Turntable, BBox */}
      <div className="absolute right-3 top-3 z-10 flex flex-col items-center gap-1 rounded-2xl border border-sky-400/25 bg-[#030d22]/85 p-1.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xl">
        {/* Snap angles */}
        <button onClick={() => snapCamera('front')} title="Vista Frontal (1)" className="grid h-7 w-7 place-items-center rounded-xl text-xs font-mono font-bold text-slate-300 hover:bg-white/10 hover:text-cyan-300">F</button>
        <button onClick={() => snapCamera('right')} title="Vista Derecha (2)" className="grid h-7 w-7 place-items-center rounded-xl text-xs font-mono font-bold text-slate-300 hover:bg-white/10 hover:text-cyan-300">R</button>
        <button onClick={() => snapCamera('top')} title="Vista Superior (5)" className="grid h-7 w-7 place-items-center rounded-xl text-xs font-mono font-bold text-slate-300 hover:bg-white/10 hover:text-cyan-300">T</button>
        <button onClick={() => snapCamera('iso')} title="Vista Isométrica (0)" className="grid h-7 w-7 place-items-center rounded-xl text-xs font-mono font-bold text-slate-300 hover:bg-white/10 hover:text-cyan-300">ISO</button>

        <div className="my-0.5 h-px w-5 bg-white/10" />

        {/* Turntable toggle */}
        <button
          onClick={() => {
            sounds.playClick();
            setTurntable((t) => !t);
          }}
          title={turntable ? 'Pausar Turntable (Espacio)' : 'Iniciar Turntable (Espacio)'}
          className={`grid h-7 w-7 place-items-center rounded-xl transition-all ${
            turntable ? 'bg-sky-500/25 text-cyan-300 border border-sky-400/30 shadow-sm' : 'text-slate-400 hover:bg-white/10'
          }`}
        >
          {turntable ? <ArrowsClockwise size={15} className="animate-spin" /> : <Play size={14} weight="fill" />}
        </button>

        {/* BBox Dimensions toggle */}
        <button
          onClick={() => {
            sounds.playClick();
            setShowBbox((b) => !b);
          }}
          title="Mostrar Cotas Métricas 3D"
          className={`grid h-7 w-7 place-items-center rounded-xl transition-all ${
            showBbox ? 'bg-sky-500/25 text-cyan-300 border border-sky-400/30' : 'text-slate-400 hover:bg-white/10'
          }`}
        >
          <Cube size={15} weight="duotone" />
        </button>

        {/* 4K Transparent PNG Capture */}
        <button
          onClick={captureSnapshot}
          title="Descargar Captura 4K PNG Transparente"
          className="grid h-7 w-7 place-items-center rounded-xl text-slate-300 hover:bg-emerald-500/20 hover:text-emerald-300 transition-all"
        >
          <DownloadSimple size={15} weight="bold" />
        </button>

        {/* Fullscreen toggle */}
        <button
          onClick={() => {
            sounds.playClick();
            setIsFullscreen((f) => !f);
          }}
          title={isFullscreen ? 'Salir de pantalla completa (ESC)' : 'Pantalla completa (F)'}
          className="grid h-7 w-7 place-items-center rounded-xl text-slate-400 hover:bg-white/10 hover:text-white"
        >
          {isFullscreen ? <CornersIn size={14} /> : <CornersOut size={14} />}
        </button>
      </div>

      {/* Bottom Live Stats Overlay Badge */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-3 rounded-2xl border border-sky-400/20 bg-[#030d22]/85 px-3.5 py-1.5 shadow-xl backdrop-blur-xl font-mono text-[10px] text-slate-300">
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
          <span className="font-bold text-white">{stats.triangles.toLocaleString()} Δ</span>
          <span className="text-slate-500">tris</span>
        </div>
        <span className="text-slate-600">|</span>
        <div className="flex items-center gap-1">
          <span className="text-cyan-300 font-bold">{stats.vertices.toLocaleString()}</span>
          <span className="text-slate-500">verts</span>
        </div>
        <span className="text-slate-600">|</span>
        <div className="flex items-center gap-1 text-sky-200">
          <span>{stats.dimensions.x} × {stats.dimensions.y} × {stats.dimensions.z} m</span>
        </div>
      </div>
    </div>
  );
}
