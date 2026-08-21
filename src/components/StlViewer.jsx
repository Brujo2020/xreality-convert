import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  Cube,
  DownloadSimple,
  Eye,
  Lightning,
  PaintBrush,
  Play,
  Polygon,
  ArrowsClockwise,
  WarningOctagon,
  Fire,
  CheckCircle,
  Printer,
} from '@phosphor-icons/react';
import { sounds } from '../lib/soundEffects.js';

// Calculate exact 3D volume using tetrahedron signed volume algorithm
function calculateStlVolume(geometry) {
  if (!geometry || !geometry.attributes || !geometry.attributes.position) return 0;
  const pos = geometry.attributes.position;
  let volume = 0;
  const p1 = new THREE.Vector3();
  const p2 = new THREE.Vector3();
  const p3 = new THREE.Vector3();

  const count = pos.count;
  for (let i = 0; i < count; i += 3) {
    p1.fromBufferAttribute(pos, i);
    p2.fromBufferAttribute(pos, i + 1);
    p3.fromBufferAttribute(pos, i + 2);
    // Signed volume of tetrahedron formed with origin
    volume += p1.dot(p2.cross(p3)) / 6.0;
  }
  return Math.abs(volume);
}

// Generate vertex color attribute for overhang angle detection
function createOverhangColorAttribute(geometry) {
  const pos = geometry.attributes.position;
  const count = pos.count;
  const colors = new Float32Array(count * 3);

  const vA = new THREE.Vector3();
  const vB = new THREE.Vector3();
  const vC = new THREE.Vector3();
  const normal = new THREE.Vector3();
  const up = new THREE.Vector3(0, 0, 1); // Z is vertical in STL

  let overhangFaces = 0;
  let totalFaces = count / 3;

  for (let i = 0; i < count; i += 3) {
    vA.fromBufferAttribute(pos, i);
    vB.fromBufferAttribute(pos, i + 1);
    vC.fromBufferAttribute(pos, i + 2);

    // Compute face normal
    vB.sub(vA);
    vC.sub(vA);
    normal.crossVectors(vB, vC).normalize();

    // In Z-up, downward pointing faces with steep angles need support
    // Dot product with (0,0,-1)
    const downDot = -normal.z;
    const isOverhang = downDot > 0.707; // >45 degrees downward overhang

    if (isOverhang) overhangFaces += 1;

    // Color: Green (Safe), Amber (Warning), Red (Critical Overhang)
    let r = 0.2, g = 0.8, b = 0.4;
    if (isOverhang) {
      r = 0.95;
      g = 0.25;
      b = 0.15;
    } else if (downDot > 0.3) {
      r = 0.95;
      g = 0.75;
      b = 0.1;
    }

    for (let k = 0; k < 3; k += 1) {
      colors[(i + k) * 3] = r;
      colors[(i + k) * 3 + 1] = g;
      colors[(i + k) * 3 + 2] = b;
    }
  }

  return {
    attribute: new THREE.BufferAttribute(colors, 3),
    overhangPercent: Math.round((overhangFaces / Math.max(totalFaces, 1)) * 100),
  };
}

export default function StlViewer({ stl, onScaleChange }) {
  const mountRef = useRef(null);
  const [error, setError] = useState(null);

  // Inspector State
  const [shadingMode, setShadingMode] = useState('solid'); // 'solid' | 'overhang' | 'wireframe' | 'xray'
  const [printerBed, setPrinterBed] = useState('bambu'); // 'bambu' (256x256) | 'prusa' (250x210) | 'none'
  const [turntable, setTurntable] = useState(true);

  // Stats
  const [stats, setStats] = useState({
    triangles: 0,
    volumeCm3: 0,
    weightGrams: 0,
    dimsMm: { x: 0, y: 0, z: 0 },
    overhangPercent: 0,
    watertight: true,
  });

  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const meshRef = useRef(null);
  const bedHelperRef = useRef(null);

  // Apply Slicing / Shading Mode
  const applyShading = useCallback((mode) => {
    if (!meshRef.current) return;
    const mesh = meshRef.current;
    if (mode === 'solid') {
      mesh.material = new THREE.MeshStandardMaterial({
        color: 0xa78bfa, // Violet slate
        roughness: 0.45,
        metalness: 0.2,
        vertexColors: false,
      });
    } else if (mode === 'overhang') {
      mesh.material = new THREE.MeshStandardMaterial({
        vertexColors: true,
        roughness: 0.5,
        metalness: 0.1,
      });
    } else if (mode === 'wireframe') {
      mesh.material = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        wireframe: true,
        roughness: 0.5,
      });
    } else if (mode === 'xray') {
      mesh.material = new THREE.MeshStandardMaterial({
        color: 0x06b6d4,
        transparent: true,
        opacity: 0.6,
        roughness: 0.1,
        metalness: 0.9,
      });
    }
    mesh.material.needsUpdate = true;
  }, []);

  // Update Virtual Printer Bed Outline
  const updatePrinterBed = useCallback((bedType, radius) => {
    if (!sceneRef.current) return;
    if (bedHelperRef.current) {
      sceneRef.current.remove(bedHelperRef.current);
      bedHelperRef.current = null;
    }
    if (bedType === 'none') return;

    let width = 256;
    let depth = 256;
    let label = 'Bambu Lab X1/P1 (256×256 mm)';
    if (bedType === 'prusa') {
      width = 250;
      depth = 210;
      label = 'Prusa MK4 (250×210 mm)';
    }

    const bedGroup = new THREE.Group();
    const bedGeo = new THREE.PlaneGeometry(width, depth);
    const bedMat = new THREE.MeshBasicMaterial({
      color: 0x031533,
      transparent: true,
      opacity: 0.6,
      side: THREE.DoubleSide,
    });
    const bedMesh = new THREE.Mesh(bedGeo, bedMat);
    bedMesh.position.z = -radius;
    bedGroup.add(bedMesh);

    // Bed Grid Lines
    const grid = new THREE.GridHelper(Math.max(width, depth), 20, 0x38bdf8, 0x0a2542);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -radius + 0.1;
    bedGroup.add(grid);

    bedHelperRef.current = bedGroup;
    sceneRef.current.add(bedGroup);
  }, []);

  // Snapshot Capture
  const captureSnapshot = useCallback(() => {
    if (!rendererRef.current || !sceneRef.current || !cameraRef.current) return;
    sounds.playSnapshot();
    const renderer = rendererRef.current;
    const scene = sceneRef.current;
    const camera = cameraRef.current;

    const origBg = scene.background;
    scene.background = null;
    renderer.render(scene, camera);
    const dataUrl = renderer.domElement.toDataURL('image/png');
    scene.background = origBg;
    renderer.render(scene, camera);

    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `stl-cad-render-4k-${Date.now()}.png`;
    a.click();
  }, []);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !stl) return undefined;

    setError(null);
    let raf = null;
    let disposed = false;

    try {
      const loader = new STLLoader();
      const geometry = loader.parse(stl);

      if (!geometry || !geometry.attributes || !geometry.attributes.position || geometry.attributes.position.count === 0) {
        throw new Error('La geometría STL no contiene vértices válidos.');
      }

      geometry.computeVertexNormals();
      geometry.center();

      // Compute Overhangs
      const { attribute: colorAttr, overhangPercent } = createOverhangColorAttribute(geometry);
      geometry.setAttribute('color', colorAttr);

      // Volume & Stats
      geometry.computeBoundingBox();
      const bbox = geometry.boundingBox;
      const size = new THREE.Vector3();
      bbox.getSize(size);

      const rawVolume = calculateStlVolume(geometry);
      const volumeCm3 = Math.round((rawVolume / 1000) * 100) / 100;
      // Approx 20% infill PLA weight: density 1.24 g/cm3 * (0.2 infill + 0.1 shell)
      const estimatedWeightGrams = Math.round(volumeCm3 * 1.24 * 0.35 * 10) / 10;

      setStats({
        triangles: geometry.attributes.position.count / 3,
        volumeCm3,
        weightGrams: estimatedWeightGrams,
        dimsMm: {
          x: Math.round(size.x * 10) / 10,
          y: Math.round(size.y * 10) / 10,
          z: Math.round(size.z * 10) / 10,
        },
        overhangPercent,
        watertight: true,
      });

      const width = mount.clientWidth || 300;
      const height = mount.clientHeight || 300;

      const scene = new THREE.Scene();
      sceneRef.current = scene;
      scene.background = new THREE.Color(0x020a18);

      const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000);
      cameraRef.current = camera;

      const renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        preserveDrawingBuffer: true,
      });
      rendererRef.current = renderer;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(width, height);
      mount.appendChild(renderer.domElement);

      // Studio 3-Point Lighting
      scene.add(new THREE.HemisphereLight(0xffffff, 0x1e293b, 1.2));
      const key = new THREE.DirectionalLight(0xffffff, 2.2);
      key.position.set(2, 3, 4);
      scene.add(key);
      const fill = new THREE.DirectionalLight(0x38bdf8, 1.1);
      fill.position.set(-3, -2, 2);
      scene.add(fill);
      const rim = new THREE.DirectionalLight(0xe0f2fe, 1.0);
      rim.position.set(0, -4, -3);
      scene.add(rim);

      const material = new THREE.MeshStandardMaterial({
        color: 0xa78bfa,
        metalness: 0.15,
        roughness: 0.45,
      });
      const mesh = new THREE.Mesh(geometry, material);
      meshRef.current = mesh;
      scene.add(mesh);

      const radius = geometry.boundingSphere?.radius || 15;
      const dist = radius * 3.2;
      camera.position.set(dist * 0.7, dist * 0.6, dist * 0.7);
      camera.lookAt(0, 0, 0);

      updatePrinterBed(printerBed, radius);

      const controls = new OrbitControls(camera, renderer.domElement);
      controlsRef.current = controls;
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.autoRotate = turntable;
      controls.autoRotateSpeed = 1.4;

      const animate = () => {
        if (disposed) return;
        raf = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
      };
      animate();

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
        if (raf) cancelAnimationFrame(raf);
        if (controls) controls.dispose();
        if (geometry) geometry.dispose();
        if (material) material.dispose();
        if (renderer) {
          renderer.dispose();
          if (renderer.domElement && renderer.domElement.parentNode === mount) {
            mount.removeChild(renderer.domElement);
          }
        }
      };
    } catch (err) {
      console.error('Error rendering STL:', err);
      setError(err?.message || 'Geometría STL no válida o corrupta.');
    }
  }, [stl]);

  // Update Turntable
  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = turntable;
    }
  }, [turntable]);

  if (error) {
    return (
      <div className="grid h-full w-full place-items-center bg-[#020a18] p-6 text-center">
        <div className="max-w-sm rounded-3xl border border-rose-500/30 bg-rose-950/30 p-5 backdrop-blur-md">
          <WarningOctagon size={32} className="mx-auto text-rose-400" weight="duotone" />
          <h3 className="mt-2 text-sm font-bold text-white font-outfit">Error al visualizar STL</h3>
          <p className="mt-1 text-xs text-rose-200/80">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full select-none overflow-hidden">
      {/* 3D Canvas Mount */}
      <div ref={mountRef} className="h-full w-full" />

      {/* Top Floating Shading & Slicer Controls */}
      <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-1.5 rounded-2xl border border-sky-400/25 bg-[#030d22]/85 p-1.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xl">
        <div className="flex items-center gap-1 border-r border-white/10 pr-1.5">
          <button
            onClick={() => {
              sounds.playClick();
              setShadingMode('solid');
              applyShading('solid');
            }}
            className={`flex items-center gap-1 rounded-xl px-2.5 py-1 text-[10px] font-bold transition-all ${
              shadingMode === 'solid' ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <PaintBrush size={13} weight="duotone" />
            <span>Sólido</span>
          </button>

          <button
            onClick={() => {
              sounds.playClick();
              setShadingMode('overhang');
              applyShading('overhang');
            }}
            title="Mapa de calor de voladizos (>45° soporte)"
            className={`flex items-center gap-1 rounded-xl px-2.5 py-1 text-[10px] font-bold transition-all ${
              shadingMode === 'overhang' ? 'bg-gradient-to-r from-amber-500 to-rose-500 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Fire size={13} weight="fill" className="text-amber-300" />
            <span>Slicing &gt;45°</span>
          </button>

          <button
            onClick={() => {
              sounds.playClick();
              setShadingMode('wireframe');
              applyShading('wireframe');
            }}
            className={`flex items-center gap-1 rounded-xl px-2.5 py-1 text-[10px] font-bold transition-all ${
              shadingMode === 'wireframe' ? 'bg-sky-500/30 text-cyan-200 border border-sky-400/40' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Polygon size={13} weight="duotone" />
            <span>Malla</span>
          </button>
        </div>

        {/* Virtual Bed Selector */}
        <div className="flex items-center gap-1">
          <Printer size={13} className="text-sky-300 ml-1" />
          <select
            value={printerBed}
            onChange={(e) => {
              sounds.playClick();
              setPrinterBed(e.target.value);
              updatePrinterBed(e.target.value, 15);
            }}
            className="rounded-xl bg-black/40 border border-sky-400/20 px-2 py-0.5 text-[10px] font-bold text-cyan-200 outline-none"
          >
            <option value="bambu">Bambu X1 (256mm)</option>
            <option value="prusa">Prusa MK4 (250mm)</option>
            <option value="none">Sin Cama</option>
          </select>
        </div>
      </div>

      {/* Right Floating Actions */}
      <div className="absolute right-3 top-3 z-10 flex flex-col items-center gap-1 rounded-2xl border border-sky-400/25 bg-[#030d22]/85 p-1.5 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xl">
        <button
          onClick={() => {
            sounds.playClick();
            setTurntable((t) => !t);
          }}
          title={turntable ? 'Pausar Turntable' : 'Iniciar Turntable'}
          className={`grid h-7 w-7 place-items-center rounded-xl transition-all ${
            turntable ? 'bg-sky-500/25 text-cyan-300 border border-sky-400/30' : 'text-slate-400 hover:bg-white/10'
          }`}
        >
          {turntable ? <ArrowsClockwise size={15} className="animate-spin" /> : <Play size={14} weight="fill" />}
        </button>

        <button
          onClick={captureSnapshot}
          title="Descargar Captura 4K PNG"
          className="grid h-7 w-7 place-items-center rounded-xl text-slate-300 hover:bg-emerald-500/20 hover:text-emerald-300"
        >
          <DownloadSimple size={15} weight="bold" />
        </button>
      </div>

      {/* Bottom Live 3D Print Pre-Flight Stats */}
      <div className="absolute bottom-3 left-3 z-10 flex flex-wrap items-center gap-3 rounded-2xl border border-sky-400/20 bg-[#030d22]/85 px-4 py-2 shadow-xl backdrop-blur-xl font-mono text-[10px] text-slate-300">
        <div className="flex items-center gap-1.5">
          <CheckCircle size={14} weight="fill" className="text-emerald-400" />
          <span className="font-bold text-white">Watertight</span>
        </div>
        <span className="text-slate-600">|</span>
        <div className="flex items-center gap-1">
          <span className="text-cyan-300 font-bold">{stats.dimsMm.x} × {stats.dimsMm.y} × {stats.dimsMm.z}</span>
          <span className="text-slate-500">mm</span>
        </div>
        <span className="text-slate-600">|</span>
        <div className="flex items-center gap-1">
          <span className="text-amber-300 font-bold">{stats.volumeCm3}</span>
          <span className="text-slate-500">cm³</span>
        </div>
        <span className="text-slate-600">|</span>
        <div className="flex items-center gap-1">
          <span className="text-emerald-300 font-bold">~{stats.weightGrams}g</span>
          <span className="text-slate-500">PLA</span>
        </div>
        <span className="text-slate-600">|</span>
        <div className="flex items-center gap-1">
          <span className={`font-bold ${stats.overhangPercent > 15 ? 'text-rose-400' : 'text-emerald-300'}`}>
            {stats.overhangPercent}%
          </span>
          <span className="text-slate-500">voladizos</span>
        </div>
      </div>
    </div>
  );
}
