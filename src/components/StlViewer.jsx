import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// Renders an ASCII STL (passed as a string) in an interactive WebGL canvas:
// drag to orbit, scroll to zoom. Re-initializes whenever the STL changes.
export default function StlViewer({ stl }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !stl) return;

    const width = mount.clientWidth;
    const height = mount.clientHeight;

    // Scene + background matching the dark theme.
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x141414);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(width, height);
    mount.appendChild(renderer.domElement);

    // Lighting: a key light, a fill, and ambient so the mesh reads well.
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(1, 1, 1);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0x8b5cf6, 0.4);
    fill.position.set(-1, -0.5, -1);
    scene.add(fill);

    // Parse + build the mesh.
    let geometry;
    try {
      geometry = new STLLoader().parse(stl);
    } catch {
      return;
    }
    geometry.computeVertexNormals();
    geometry.center();

    const material = new THREE.MeshStandardMaterial({
      color: 0x9b7cf0,
      metalness: 0.1,
      roughness: 0.6,
      flatShading: false,
    });
    const mesh = new THREE.Mesh(geometry, material);
    // STL is Z-up; rotate so it sits naturally for the viewer (Y-up).
    mesh.rotation.x = -Math.PI / 2;
    scene.add(mesh);

    // Frame the camera around the model's bounding sphere.
    geometry.computeBoundingSphere();
    const radius = geometry.boundingSphere?.radius || 10;
    const dist = radius * 2.6;
    camera.position.set(dist * 0.7, dist * 0.6, dist * 0.7);
    camera.lookAt(0, 0, 0);

    const grid = new THREE.GridHelper(radius * 4, 20, 0x333333, 0x222222);
    grid.position.y = -radius;
    scene.add(grid);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 0, 0);

    let raf;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Keep the canvas sized to its container.
    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (w === 0 || h === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [stl]);

  return <div ref={mountRef} className="h-full w-full" />;
}
