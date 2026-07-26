import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { embeddedBaseColorImage } from '../lib/glbTextures.js';
import {
  CANONICAL_ORBIT_VIEWS,
  CANONICAL_RENDER_PROFILE,
  cameraDistanceForRadius,
  cameraPositionForView,
} from '../lib/canonicalViews.js';

// Decode a base64 string into an ArrayBuffer for GLTFLoader.parse().
function base64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const len = bin.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

async function sha256Hex(blob) {
  const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

function canvasPng(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('png_capture_failed'))),
      'image/png',
    );
  });
}

const TEXTURE_SLOTS = [
  ['map', 'Albedo'],
  ['metalnessMap', 'Metalness'],
  ['roughnessMap', 'Roughness'],
  ['normalMap', 'Normal'],
  ['aoMap', 'AO'],
  ['emissiveMap', 'Emissive'],
  ['alphaMap', 'Alpha'],
];

function inspectLoadedModel(model) {
  const materials = new Set();
  const texturedMaterials = new Set();
  const slots = new Set();
  const textures = new Set();
  model.traverse((object) => {
    const objectMaterials = Array.isArray(object.material) ? object.material : [object.material];
    objectMaterials.filter(Boolean).forEach((material) => {
      materials.add(material);
      TEXTURE_SLOTS.forEach(([key, label]) => {
        const texture = material[key];
        if (texture?.isTexture) {
          slots.add(label);
          textures.add(texture.uuid || texture);
          texturedMaterials.add(material);
        }
      });
    });
  });
  return {
    materialCount: materials.size,
    texturedMaterialCount: texturedMaterials.size,
    textureCount: textures.size,
    textureSlots: Array.from(slots),
  };
}

// Renders a GLB (passed as base64) in an interactive WebGL canvas:
// drag to orbit, scroll to zoom. Keeps the model's own materials/colors.
export default function GltfViewer({ glbBase64, onInspection, onCanonicalRenders }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !glbBase64) return;
    const glbBuffer = base64ToArrayBuffer(glbBase64);

    const width = mount.clientWidth;
    const height = mount.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x030d20);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 5000);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      preserveDrawingBuffer: true,
      powerPreference: 'high-performance',
      stencil: false,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    mount.appendChild(renderer.domElement);

    const roomEnvironment = new RoomEnvironment();
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    const environmentTarget = pmremGenerator.fromScene(roomEnvironment, 0.04);
    scene.environment = environmentTarget.texture;
    roomEnvironment.dispose();
    pmremGenerator.dispose();

    scene.add(new THREE.HemisphereLight(0xffffff, 0x52606d, 0.8));
    const key = new THREE.DirectionalLight(0xfff7ed, 2.2);
    key.position.set(2.5, 4, 3);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xdbeafe, 1.1);
    fill.position.set(-3, 1.5, 2);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(0xffffff, 1.4);
    rim.position.set(0, 3, -4);
    scene.add(rim);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;

    let raf;
    let disposed = false;
    let fallbackTexture = null;
    let fallbackBitmap = null;
    const canonicalObjectUrls = [];
    const renderOnce = () => renderer.render(scene, camera);
    controls.addEventListener('change', renderOnce);

    const loader = new GLTFLoader();
    loader.parse(
      glbBuffer,
      '',
      (gltf) => {
        if (disposed) return;
        const model = gltf.scene;
        let inspection = inspectLoadedModel(model);
        let fallbackReady = Promise.resolve();
        if (!inspection.textureCount) {
          const embeddedImage = embeddedBaseColorImage(glbBuffer);
          if (embeddedImage) {
            fallbackReady = createImageBitmap(new Blob([embeddedImage.bytes], { type: embeddedImage.mimeType }))
              .then((bitmap) => {
              fallbackBitmap = bitmap;
              if (disposed) return;
              fallbackTexture = new THREE.Texture(bitmap);
              fallbackTexture.colorSpace = THREE.SRGBColorSpace;
              fallbackTexture.flipY = false;
              fallbackTexture.needsUpdate = true;
              model.traverse((object) => {
                const materials = Array.isArray(object.material) ? object.material : [object.material];
                materials.filter(Boolean).forEach((material) => {
                  if (!material.map) material.map = fallbackTexture;
                  material.metalness = 0;
                  material.roughness = 1;
                  material.needsUpdate = true;
                });
              });
              inspection = inspectLoadedModel(model);
              onInspection?.(inspection);
              renderOnce();
              })
              .catch((error) => {
                onInspection?.({ ...inspection, error: `No se pudo decodificar la textura: ${error.message}` });
              });
          }
        }
        onInspection?.(inspection);

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

        const grid = new THREE.GridHelper(radius * 4, 20, 0x1689e8, 0x0b2543);
        grid.position.y = -radius;
        scene.add(grid);
        renderOnce();

        const captureCanonicalRenders = async () => {
          if (!onCanonicalRenders || disposed) return;
          const originalSize = renderer.getSize(new THREE.Vector2());
          const originalPixelRatio = renderer.getPixelRatio();
          const originalBackground = scene.background;
          const originalPosition = camera.position.clone();
          const originalQuaternion = camera.quaternion.clone();
          const originalFov = camera.fov;
          const originalAspect = camera.aspect;
          const originalNear = camera.near;
          const originalFar = camera.far;
          const distance = cameraDistanceForRadius(radius);
          const views = [];
          const startedAt = performance.now();
          let encodedBytes = 0;
          try {
            grid.visible = false;
            scene.background = new THREE.Color(CANONICAL_RENDER_PROFILE.background);
            renderer.setPixelRatio(1);
            renderer.setSize(
              CANONICAL_RENDER_PROFILE.width,
              CANONICAL_RENDER_PROFILE.height,
              false,
            );
            camera.fov = CANONICAL_RENDER_PROFILE.fovDegrees;
            camera.aspect = 1;
            camera.near = radius / 100;
            camera.far = radius * 100;
            camera.updateProjectionMatrix();
            for (const view of CANONICAL_ORBIT_VIEWS) {
              const position = cameraPositionForView(view, distance);
              camera.position.set(position.x, position.y, position.z);
              camera.up.set(0, 1, 0);
              camera.lookAt(0, 0, 0);
              camera.updateMatrixWorld(true);
              renderer.render(scene, camera);
              const blob = await canvasPng(renderer.domElement);
              const imageUrl = URL.createObjectURL(blob);
              canonicalObjectUrls.push(imageUrl);
              encodedBytes += blob.size;
              views.push({
                ...view,
                width: CANONICAL_RENDER_PROFILE.width,
                height: CANONICAL_RENDER_PROFILE.height,
                imageSha256: await sha256Hex(blob),
                imageUrl,
                encodedBytes: blob.size,
                cameraMatrix: camera.matrixWorld.elements.slice(),
              });
            }
            onCanonicalRenders({
              profileVersion: CANONICAL_RENDER_PROFILE.version,
              views,
              warnings: [],
              performance: {
                captureDurationMs: Math.round(performance.now() - startedAt),
                encodedBytes,
                retainedCopiesPerView: 1,
              },
            });
          } catch (error) {
            onCanonicalRenders({
              profileVersion: CANONICAL_RENDER_PROFILE.version,
              views,
              warnings: [error.message || 'canonical_render_failed'],
              performance: {
                captureDurationMs: Math.round(performance.now() - startedAt),
                encodedBytes,
                retainedCopiesPerView: 1,
              },
            });
          } finally {
            camera.position.copy(originalPosition);
            camera.quaternion.copy(originalQuaternion);
            camera.fov = originalFov;
            camera.aspect = originalAspect;
            camera.near = originalNear;
            camera.far = originalFar;
            camera.updateProjectionMatrix();
            scene.background = originalBackground;
            grid.visible = true;
            renderer.setPixelRatio(originalPixelRatio);
            renderer.setSize(originalSize.x, originalSize.y, false);
            renderOnce();
          }
        };

        fallbackReady.finally(captureCanonicalRenders);
      },
      (err) => {
        console.error('GLB parse error', err);
      }
    );

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      renderOnce();
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.removeEventListener('change', renderOnce);
      controls.dispose();
      fallbackTexture?.dispose?.();
      fallbackBitmap?.close?.();
      canonicalObjectUrls.forEach((url) => URL.revokeObjectURL(url));
      environmentTarget.dispose();
      scene.traverse((object) => {
        object.geometry?.dispose?.();
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        materials.filter(Boolean).forEach((material) => {
          Object.values(material).forEach((value) => {
            if (value?.isTexture) value.dispose();
          });
          material.dispose?.();
        });
      });
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [glbBase64, onInspection, onCanonicalRenders]);

  return <div ref={mountRef} className="h-full w-full" />;
}
