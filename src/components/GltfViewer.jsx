import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// Decode a base64 string into an ArrayBuffer for GLTFLoader.parse().
function base64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const len = bin.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

// Renders a GLB (passed as base64) in an interactive WebGL canvas:
// drag to orbit, scroll to zoom. Keeps the model's own materials/colors.
export default function GltfViewer({ glbBase64 }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !glbBase64) return;

    const width = mount.clientWidth;
    const height = mount.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x141414);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 5000);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 1.2);
    key.position.set(1, 1.5, 1);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0x8b5cf6, 0.5);
    fill.position.set(-1, -0.5, -1);
    scene.add(fill);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    let raf;
    let disposed = false;

    const loader = new GLTFLoader();
    loader.parse(
      base64ToArrayBuffer(glbBase64),
      '',
      (gltf) => {
        if (disposed) return;
        const model = gltf.scene;

        // Center + frame the model.
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        model.position.sub(center);
        scene.add(model);

        const radius = Math.max(size.x, size.y, size.z) * 0.5 || 1;
        const dist = radius * 3;
        camera.position.set(dist * 0.6, dist * 0.5, dist * 0.9);
        camera.near = radius / 100;
        camera.far = radius * 100;
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.update();

        const grid = new THREE.GridHelper(radius * 4, 20, 0x333333, 0x222222);
        grid.position.y = -radius;
        scene.add(grid);
      },
      (err) => {
        console.error('GLB parse error', err);
      }
    );

    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [glbBase64]);

  return <div ref={mountRef} className="h-full w-full" />;
}
