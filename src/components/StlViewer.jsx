import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { WarningOctagon } from '@phosphor-icons/react';

// Renders an ASCII or Binary STL in an interactive WebGL canvas:
// drag to orbit, scroll to zoom. Re-initializes whenever the STL changes.
export default function StlViewer({ stl }) {
  const mountRef = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !stl) return undefined;

    let geometry = null;
    let renderer = null;
    let controls = null;
    let material = null;
    let mesh = null;
    let grid = null;
    let raf = null;
    let ro = null;
    let disposed = false;

    try {
      const loader = new STLLoader();
      geometry = loader.parse(stl);
      if (!geometry || !geometry.attributes || !geometry.attributes.position || geometry.attributes.position.count === 0) {
        throw new Error('La geometría STL no contiene vértices válidos.');
      }
    } catch (err) {
      console.error('Error parsing STL:', err);
      setError(err?.message || 'Geometría STL no válida o corrupta.');
      return undefined;
    }

    setError(null);

    const width = mount.clientWidth || 300;
    const height = mount.clientHeight || 300;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x030d20);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000);

    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(width, height);
      mount.appendChild(renderer.domElement);
    } catch (webglErr) {
      console.error('WebGL context creation failed:', webglErr);
      setError('No se pudo inicializar el contexto 3D WebGL.');
      geometry.dispose();
      return undefined;
    }

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(1, 1, 1);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0x35a7ff, 0.55);
    fill.position.set(-1, -0.5, -1);
    scene.add(fill);

    geometry.computeVertexNormals();
    geometry.center();

    material = new THREE.MeshStandardMaterial({
      color: 0x9b7cf0,
      metalness: 0.1,
      roughness: 0.6,
      flatShading: false,
    });
    mesh = new THREE.Mesh(geometry, material);
    mesh.rotation.x = -Math.PI / 2;
    scene.add(mesh);

    geometry.computeBoundingSphere();
    const radius = geometry.boundingSphere?.radius || 10;
    const dist = radius * 2.6;
    camera.position.set(dist * 0.7, dist * 0.6, dist * 0.7);
    camera.lookAt(0, 0, 0);

    grid = new THREE.GridHelper(radius * 4, 20, 0x333333, 0x222222);
    grid.position.y = -radius;
    scene.add(grid);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 0, 0);

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
    ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      disposed = true;
      if (raf) cancelAnimationFrame(raf);
      if (ro) ro.disconnect();
      if (controls) controls.dispose();
      if (geometry) geometry.dispose();
      if (material) material.dispose();
      if (grid) {
        grid.geometry?.dispose();
        grid.material?.dispose();
      }
      if (renderer) {
        renderer.dispose();
        renderer.forceContextLoss();
        if (renderer.domElement && renderer.domElement.parentNode === mount) {
          mount.removeChild(renderer.domElement);
        }
      }
    };
  }, [stl]);

  if (error) {
    return (
      <div className="grid h-full w-full place-items-center bg-[#030d20] p-6 text-center">
        <div className="max-w-sm rounded-2xl border border-rose-500/20 bg-rose-950/20 p-5 backdrop-blur-md">
          <WarningOctagon size={28} className="mx-auto text-rose-300" weight="duotone" />
          <h3 className="mt-2 text-sm font-semibold text-white">Error al visualizar STL</h3>
          <p className="mt-1 text-xs text-rose-200/80">{error}</p>
        </div>
      </div>
    );
  }

  return <div ref={mountRef} className="h-full w-full" />;
}
