import React, { useEffect, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { Camera, CheckCircle, Eye, SpinnerGap, Sparkle } from '@phosphor-icons/react';

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

function capture6CanonicalViews(gltfScene, width = 512, height = 512) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020817);

  const model = gltfScene.clone(true);
  model.traverse((object) => {
    if (object.isMesh) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((mat) => {
        if (!mat) return;
        if (mat.map) {
          mat.map.colorSpace = THREE.SRGBColorSpace;
          mat.map.needsUpdate = true;
        }
        if (!mat.map && (!mat.color || mat.color.getHex() === 0xffffff || mat.color.getHex() === 0x000000)) {
          mat.color = new THREE.Color(0x94a3b8);
          mat.roughness = 0.62;
          mat.metalness = 0.12;
        } else {
          if (mat.clearcoat !== undefined && mat.clearcoat > 0.25) {
            mat.clearcoat = 0.12;
            mat.clearcoatRoughness = 0.45;
          }
          if (mat.roughness !== undefined && mat.roughness < 0.35 && (!mat.metalness || mat.metalness < 0.5)) {
            mat.roughness = 0.52;
          }
        }
        mat.needsUpdate = true;
      });
    }
  });

  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  model.position.sub(center);
  scene.add(model);

  // Balanced studio lighting
  scene.add(new THREE.HemisphereLight(0xffffff, 0x1e293b, 1.2));
  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(4, 6, 5);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xfff6ee, 1.3);
  fill.position.set(-5, 2, 3);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xe2e8f0, 0.9);
  rim.position.set(1, 4, -5);
  scene.add(rim);
  const bottomBounce = new THREE.DirectionalLight(0x475569, 0.35);
  bottomBounce.position.set(0, -4, 1);
  scene.add(bottomBounce);

  const radius = Math.max(size.x, size.y, size.z) * 0.5 || 1;
  const dist = radius * 2.85;

  const camera = new THREE.PerspectiveCamera(40, width / height, 0.01, 1000);
  camera.near = Math.max(radius / 100, 0.001);
  camera.far = radius * 100;

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    preserveDrawingBuffer: true,
    powerPreference: 'high-performance',
  });
  renderer.setSize(width, height);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;

  const angles = [
    { id: 'front', pos: [0, 0, dist], up: [0, 1, 0] },
    { id: 'right', pos: [dist, 0, 0], up: [0, 1, 0] },
    { id: 'back', pos: [0, 0, -dist], up: [0, 1, 0] },
    { id: 'left', pos: [-dist, 0, 0], up: [0, 1, 0] },
    { id: 'top', pos: [0, dist, 0.0001], up: [0, 0, -1] },
    { id: 'bottom', pos: [0, -dist, 0.0001], up: [0, 0, 1] },
  ];

  const results = {};
  for (const angle of angles) {
    camera.position.set(angle.pos[0], angle.pos[1], angle.pos[2]);
    camera.up.set(angle.up[0], angle.up[1], angle.up[2]);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);
    results[angle.id] = canvas.toDataURL('image/png');
  }

  renderer.dispose();
  return results;
}

export default function MultiViewGrid({ views, mainImage, inputDataUrl, glbBase64, glbPath, result }) {
  const effectiveGlbPath = glbPath || result?.glbPath;
  const effectiveGlbBase64 = glbBase64 || result?.glbBase64;
  const fallbackImg = mainImage || inputDataUrl || result?.inputDataUrl;

  const [renderedViews, setRenderedViews] = useState({});
  const [rendering3d, setRendering3d] = useState(false);
  const [selectedView, setSelectedView] = useState(null);

  // If 2D view images are not all present, render them from the 3D model
  useEffect(() => {
    let active = true;
    const hasAllViews = views && views.front && views.right && views.back && views.left && views.top && views.bottom;
    if (hasAllViews) {
      setRenderedViews(views);
      return;
    }

    if (!effectiveGlbPath && !effectiveGlbBase64) {
      if (fallbackImg) {
        setRenderedViews((curr) => ({ ...curr, front: curr.front || fallbackImg }));
      }
      return;
    }

    setRendering3d(true);
    const loader = new GLTFLoader();

    const onModelLoaded = (gltf) => {
      if (!active) return;
      try {
        const captured = capture6CanonicalViews(gltf.scene);
        if (active) {
          setRenderedViews({
            front: views?.front || captured.front || fallbackImg,
            right: views?.right || captured.right,
            back: views?.back || captured.back,
            left: views?.left || captured.left,
            top: views?.top || captured.top,
            bottom: views?.bottom || captured.bottom,
          });
          setRendering3d(false);
        }
      } catch (err) {
        console.error('Failed to render 6 views from 3D model:', err);
        if (active) setRendering3d(false);
      }
    };

    const onModelError = (err) => {
      console.warn('GLTF load for 6 views failed:', err);
      if (effectiveGlbBase64 && effectiveGlbPath && active) {
        const buf = base64ToArrayBuffer(effectiveGlbBase64);
        if (buf.byteLength > 0) {
          loader.parse(buf, '', onModelLoaded, () => active && setRendering3d(false));
          return;
        }
      }
      if (active) setRendering3d(false);
    };

    if (effectiveGlbPath) {
      loader.load(localFileUrl(effectiveGlbPath), onModelLoaded, undefined, onModelError);
    } else if (effectiveGlbBase64) {
      const buf = base64ToArrayBuffer(effectiveGlbBase64);
      if (buf.byteLength > 0) {
        loader.parse(buf, '', onModelLoaded, onModelError);
      } else {
        setRendering3d(false);
      }
    }

    return () => {
      active = false;
    };
  }, [views, effectiveGlbPath, effectiveGlbBase64, fallbackImg]);

  const viewCards = [
    { id: 'front', label: 'Frontal (0°)', desc: 'Cámara Principal', image: renderedViews.front || views?.front || fallbackImg },
    { id: 'right', label: 'Derecha (90°)', desc: 'Perfil Lateral', image: renderedViews.right || views?.right },
    { id: 'back', label: 'Trasera (180°)', desc: 'Vista Posterior', image: renderedViews.back || views?.back },
    { id: 'left', label: 'Izquierda (270°)', desc: 'Perfil Opuesto', image: renderedViews.left || views?.left },
    { id: 'top', label: 'Superior (+90°)', desc: 'Cenital', image: renderedViews.top || views?.top },
    { id: 'bottom', label: 'Inferior (-90°)', desc: 'Base / Chasis', image: renderedViews.bottom || views?.bottom },
  ];

  const formatSrc = (img) => {
    if (!img) return '';
    if (img.startsWith('data:') || img.startsWith('http') || img.startsWith('blob:')) return img;
    return `data:image/png;base64,${img}`;
  };

  return (
    <div className="flex h-full w-full flex-col gap-3 p-4 overflow-y-auto select-none font-sans">
      <div className="flex items-center justify-between border-b border-sky-400/20 pb-3">
        <div>
          <span className="flex items-center gap-1.5 font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-cyan-300">
            <Sparkle size={13} weight="fill" className="text-amber-300" />
            Evidencia & Cobertura Multi-Vista 3D PBR
          </span>
          <h2 className="text-sm font-bold tracking-tight text-white flex items-center gap-2 mt-0.5">
            Matriz de Proyección 6 Vistas Canónicas
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {rendering3d && (
            <span className="flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 font-mono text-[9px] font-semibold text-amber-200 animate-pulse">
              <SpinnerGap size={12} className="animate-spin" /> Renderizando matriz 3D…
            </span>
          )}
          <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 font-mono text-[9px] font-semibold text-cyan-200">
            6 Vistas Sincronizadas
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 flex-1 min-h-0">
        {viewCards.map((item) => {
          const hasImage = Boolean(item.image);

          return (
            <div
              key={item.id}
              onClick={() => hasImage && setSelectedView(item)}
              className={`group relative flex flex-col justify-between overflow-hidden rounded-2xl border transition-all duration-300 ${
                hasImage
                  ? 'border-sky-400/30 bg-[#030e22]/90 shadow-[0_0_25px_rgba(56,189,248,0.12)] hover:border-cyan-300/60 hover:scale-[1.015] cursor-pointer'
                  : 'border-dashed border-white/10 bg-white/[0.02]'
              }`}
            >
              <div className="absolute top-2.5 left-2.5 z-10 flex items-center gap-1.5 rounded-full border border-white/15 bg-black/75 px-3 py-1 backdrop-blur-md">
                <Camera size={12} className={hasImage ? 'text-cyan-300' : 'text-slate-500'} />
                <span className="font-mono text-[9px] font-bold uppercase text-slate-100">
                  {item.label}
                </span>
              </div>

              {hasImage ? (
                <div className="relative flex flex-1 items-center justify-center p-3 pt-9">
                  <img
                    src={formatSrc(item.image)}
                    alt={item.label}
                    className="max-h-36 w-full rounded-xl object-contain transition duration-300 group-hover:scale-105"
                  />
                  <div className="absolute bottom-2 right-2 flex items-center gap-1">
                    <span className="rounded-full border border-emerald-400/40 bg-emerald-400/20 p-1 text-emerald-300 shadow-md">
                      <CheckCircle size={13} weight="fill" />
                    </span>
                    <span className="opacity-0 group-hover:opacity-100 transition-opacity rounded-full border border-sky-400/40 bg-sky-500/30 p-1 text-sky-200">
                      <Eye size={13} weight="bold" />
                    </span>
                  </div>
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center p-4 text-center">
                  <SpinnerGap size={22} className="text-cyan-400 animate-spin mb-2" />
                  <span className="text-[11px] text-slate-300 font-medium">Sintetizando {item.label}…</span>
                  <span className="text-[8px] font-mono text-cyan-300/70 mt-0.5">{item.desc}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Lightbox / Zoom Modal for individual view inspection */}
      {selectedView && (
        <div
          onClick={() => setSelectedView(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6 backdrop-blur-md animate-fadeIn"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative max-w-2xl w-full rounded-3xl border border-sky-400/30 bg-[#030d22] p-5 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Camera size={18} className="text-cyan-300" />
                <h3 className="font-bold text-white text-base">{selectedView.label} · {selectedView.desc}</h3>
              </div>
              <button
                onClick={() => setSelectedView(null)}
                className="rounded-full bg-white/10 hover:bg-white/20 text-slate-300 px-3 py-1 text-xs font-bold transition"
              >
                Cerrar ✕
              </button>
            </div>
            <div className="flex items-center justify-center p-4 bg-black/60 rounded-2xl border border-white/5">
              <img
                src={formatSrc(selectedView.image)}
                alt={selectedView.label}
                className="max-h-[60vh] max-w-full rounded-xl object-contain shadow-2xl"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
