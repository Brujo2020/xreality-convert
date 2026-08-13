import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { WarningOctagon } from '@phosphor-icons/react';

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

export default function GltfViewer({ glbBase64, glbPath }) {
  const mountRef = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || (!glbPath && !glbBase64)) return undefined;

    setError(null);

    let scene, camera, renderer, controls;
    let model = null;
    let floor = null;
    let grid = null;
    let animationFrame = null;
    let disposed = false;
    let inViewport = true;
    let resizeObserver = null;
    let intersectionObserver = null;

    try {
      scene = new THREE.Scene();
      scene.background = new THREE.Color(0x020b1a);
      scene.fog = new THREE.FogExp2(0x020b1a, 0.035);

      camera = new THREE.PerspectiveCamera(38, 1, 0.01, 5000);

      renderer = new THREE.WebGLRenderer({
        antialias: false,
        alpha: false,
        depth: true,
        stencil: false,
        powerPreference: 'default',
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      renderer.shadowMap.enabled = false;
      mount.appendChild(renderer.domElement);

      scene.add(new THREE.HemisphereLight(0xe6f7ff, 0x07101f, 2.2));
      const key = new THREE.DirectionalLight(0xfff4e8, 3.2);
      key.position.set(3, 5, 4);
      scene.add(key);
      const rim = new THREE.DirectionalLight(0x52d7ff, 2.2);
      rim.position.set(-4, 2, -3);
      scene.add(rim);
      const fill = new THREE.DirectionalLight(0x38bdf8, 1.4);
      fill.position.set(-3, -2, 4);
      scene.add(fill);

      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.075;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 1.2;
      controls.minPolarAngle = 0.15;
      controls.maxPolarAngle = Math.PI * 0.92;
    } catch (initErr) {
      console.error('Failed to init Three.js renderer for GLTF:', initErr);
      setError('No se pudo iniciar el motor WebGL 3D.');
      return undefined;
    }

    const renderFrame = () => {
      if (disposed || document.hidden || !inViewport) {
        animationFrame = null;
        return;
      }
      controls.update();
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(renderFrame);
    };

    const resume = () => {
      if (!animationFrame && !disposed && !document.hidden && inViewport) renderFrame();
    };

    const loader = new GLTFLoader();

    const onLoaded = (gltf) => {
      if (disposed) return;
      model = gltf.scene;
      model.traverse((object) => {
        if (object.isMesh) {
          object.castShadow = false;
          object.receiveShadow = false;
          if (object.material) object.material.envMapIntensity = 0;
        }
      });

      const box = new THREE.Box3().setFromObject(model);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      model.position.sub(center);
      scene.add(model);

      const radius = Math.max(size.x, size.y, size.z) * 0.5 || 1;
      const distance = radius * 4.6;
      camera.position.set(distance * 0.18, distance * 0.12, distance);
      camera.lookAt(0, 0, 0);
      camera.near = Math.max(radius / 100, 0.001);
      camera.far = radius * 100;
      camera.updateProjectionMatrix();
      controls.target.set(0, 0, 0);
      controls.update();

      floor = new THREE.Mesh(
        new THREE.CircleGeometry(radius * 3.4, 64),
        new THREE.MeshBasicMaterial({ color: 0x020817, transparent: true, opacity: 0.72 })
      );
      floor.rotation.x = -Math.PI / 2;
      floor.position.y = -radius * 1.03;
      scene.add(floor);

      grid = new THREE.GridHelper(radius * 5, 24, 0x1689e8, 0x0a2542);
      grid.position.y = -radius * 1.02;
      (Array.isArray(grid.material) ? grid.material : [grid.material]).forEach((material) => {
        material.opacity = 0.34;
        material.transparent = true;
      });
      scene.add(grid);
      resume();
    };

    const onLoadError = (loadFailure) => {
      if (disposed) return;
      if (glbBase64 && glbPath) {
        // Fallback from path to base64 if path load fails
        const buffer = base64ToArrayBuffer(glbBase64);
        if (buffer.byteLength > 0) {
          loader.parse(buffer, '', onLoaded, (fallbackFailure) => {
            console.error('GLB parse fallback error', fallbackFailure);
            setError('Error al decodificar la geometría GLB 3D.');
          });
          return;
        }
      }
      console.error('GLB parse error', loadFailure);
      setError('No se pudo cargar el archivo GLB 3D.');
    };

    if (glbPath) {
      loader.load(localFileUrl(glbPath), onLoaded, undefined, onLoadError);
    } else if (glbBase64) {
      const buffer = base64ToArrayBuffer(glbBase64);
      if (buffer.byteLength > 0) {
        loader.parse(buffer, '', onLoaded, onLoadError);
      } else {
        setError('El búfer del modelo GLB está vacío o corrupto.');
      }
    }

    const resize = () => {
      if (disposed || !mount) return;
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      renderer.render(scene, camera);
    };

    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(mount);

    intersectionObserver = new IntersectionObserver(([entry]) => {
      inViewport = entry.isIntersecting;
      if (inViewport) resume();
    });
    intersectionObserver.observe(mount);

    document.addEventListener('visibilitychange', resume);
    resize();
    resume();

    return () => {
      disposed = true;
      if (animationFrame) cancelAnimationFrame(animationFrame);
      document.removeEventListener('visibilitychange', resume);
      if (resizeObserver) resizeObserver.disconnect();
      if (intersectionObserver) intersectionObserver.disconnect();
      if (controls) controls.dispose();
      if (model) disposeObject(model);
      if (floor) {
        floor.geometry?.dispose();
        floor.material?.dispose();
      }
      if (grid) disposeObject(grid);
      if (renderer) {
        renderer.renderLists?.dispose();
        renderer.dispose();
        renderer.forceContextLoss();
        if (renderer.domElement && renderer.domElement.parentNode === mount) {
          mount.removeChild(renderer.domElement);
        }
      }
    };
  }, [glbBase64, glbPath]);

  if (error) {
    return (
      <div className="grid h-full w-full place-items-center bg-[#020b1a] p-6 text-center">
        <div className="max-w-sm rounded-2xl border border-rose-500/20 bg-rose-950/20 p-5 backdrop-blur-md">
          <WarningOctagon size={28} className="mx-auto text-rose-300" weight="duotone" />
          <h3 className="mt-2 text-sm font-semibold text-white">Error al cargar modelo 3D</h3>
          <p className="mt-1 text-xs text-rose-200/80">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={mountRef} className="relative h-full w-full">
      <div className="pointer-events-none absolute bottom-3 right-3 z-10 rounded-full border border-sky-400/25 bg-[#020917]/85 px-3.5 py-1.5 font-mono text-[8px] font-bold uppercase tracking-[0.16em] text-sky-200 backdrop-blur-xl shadow-lg">
        🖱️ Arrastra para girar · Rueda para zoom
      </div>
    </div>
  );
}
