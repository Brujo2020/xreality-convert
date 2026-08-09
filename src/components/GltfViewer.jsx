import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

function base64ToArrayBuffer(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes.buffer;
}

function localFileUrl(filePath) {
  return `file://${String(filePath).split('/').map((part) => encodeURIComponent(part)).join('/')}`;
}

function disposeObject(root) {
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

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || (!glbPath && !glbBase64)) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020b1a);
    scene.fog = new THREE.FogExp2(0x020b1a, 0.035);

    const camera = new THREE.PerspectiveCamera(38, 1, 0.01, 5000);
    // PMREM RoomEnvironment plus dynamic shadows can compile dozens of Metal
    // shader variants in ANGLE and has crashed the Electron renderer on Apple
    // Silicon. Keep one lean context; direct lights still render glTF PBR well.
    const renderer = new THREE.WebGLRenderer({
      antialias: false,
      alpha: false,
      depth: true,
      stencil: false,
      powerPreference: 'default',
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = false;
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xe6f7ff, 0x07101f, 2.0));
    const key = new THREE.DirectionalLight(0xfff4e8, 3.2);
    key.position.set(3, 5, 4);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x52d7ff, 2.0);
    rim.position.set(-4, 2, -3);
    scene.add(rim);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.075;
    controls.minPolarAngle = 0.15;
    controls.maxPolarAngle = Math.PI * 0.92;

    let model = null;
    let floor = null;
    let grid = null;
    let animationFrame = null;
    let disposed = false;
    let inViewport = true;

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
      if (glbBase64) {
        loader.parse(base64ToArrayBuffer(glbBase64), '', onLoaded, (fallbackFailure) => {
          console.error('GLB parse error', fallbackFailure);
        });
        return;
      }
      console.error('GLB parse error', loadFailure);
    };
    if (glbPath) {
      loader.load(localFileUrl(glbPath), onLoaded, undefined, onLoadError);
    } else {
      loader.parse(base64ToArrayBuffer(glbBase64), '', onLoaded, onLoadError);
    }

    const resize = () => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      renderer.render(scene, camera);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(mount);

    const intersectionObserver = new IntersectionObserver(([entry]) => {
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
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      controls.dispose();
      if (model) disposeObject(model);
      floor?.geometry.dispose();
      floor?.material.dispose();
      if (grid) disposeObject(grid);
      renderer.renderLists.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, [glbBase64, glbPath]);

  return (
    <div ref={mountRef} className="relative h-full w-full">
      <div className="pointer-events-none absolute bottom-3 right-3 z-10 rounded-lg border border-white/10 bg-black/35 px-2.5 py-1.5 font-mono text-[7px] uppercase tracking-[0.14em] text-slate-400 backdrop-blur-md">Arrastra · rueda para zoom</div>
    </div>
  );
}
