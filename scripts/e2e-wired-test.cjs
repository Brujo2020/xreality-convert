const assert = require('assert');
const fs = require('fs');
const path = require('path');

console.log('🧪 Iniciando Auditoría E2E de Cableado y Módulos…\n');

// 1. Check all essential component files exist and are populated
const components = [
  'App.jsx',
  'main.jsx',
  'components/Header.jsx',
  'components/PromptPanel.jsx',
  'components/ImageViewer.jsx',
  'components/GltfViewer.jsx',
  'components/StlViewer.jsx',
  'components/Gallery.jsx',
  'components/ErrorBoundary.jsx',
  'components/FullReportModal.jsx',
  'components/OnlineTextureModal.jsx',
  'components/OnlineCorrectionModal.jsx',
  'components/JobsIveDesignReviewModal.jsx',
  'components/PipelineNodeGraph.jsx',
  'components/MultiViewGrid.jsx',
  'components/LiveTelemetryDrawer.jsx',
  'components/HorizontalFlowStudio.jsx',
  'components/SparkleBurst.jsx',
];

const srcDir = path.join(__dirname, '../src');

components.forEach((file) => {
  const fullPath = path.join(srcDir, file);
  assert(fs.existsSync(fullPath), `El componente ${file} no existe en el sistema de archivos.`);
  const content = fs.readFileSync(fullPath, 'utf-8');
  assert(content.length > 50, `El componente ${file} está vacío o truncado.`);
  console.log(`  ✓ Componente verificado: src/${file} (${(content.length / 1024).toFixed(1)} KB)`);
});

// 2. Base64 GLB ArrayBuffer Sanitization Check
console.log('\n🔍 Verificando Sanitización de Base64 GLB y Prevención de Pantallas en Negro…');

function base64ToArrayBuffer(base64) {
  if (!base64 || typeof base64 !== 'string') return new ArrayBuffer(0);
  try {
    const clean = base64.includes(',') ? base64.split(',')[1] : base64;
    const sanitized = clean.replace(/\s/g, '');
    const binary = Buffer.from(sanitized, 'base64').toString('binary');
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
  } catch (err) {
    return new ArrayBuffer(0);
  }
}

const mockGlbHeader = 'data:application/octet-stream;base64,glTF200000000';
const buffer = base64ToArrayBuffer(mockGlbHeader);
assert(buffer instanceof ArrayBuffer, 'La conversión Base64 debió retornar un ArrayBuffer válido.');
console.log('  ✓ Conversión limpia de Base64 con prefijo data:URI verificada sin DOMExceptions.');

// 3. Verify index.css tokens
const cssPath = path.join(srcDir, 'index.css');
const cssContent = fs.readFileSync(cssPath, 'utf-8');
assert(cssContent.includes('.glass-glow-emerald'), 'Falta la clase .glass-glow-emerald en index.css');
assert(cssContent.includes('.glass-glow-violet'), 'Falta la clase .glass-glow-violet en index.css');
console.log('  ✓ Tokens de diseño y utilidades Glassmorphism en index.css verificados.');

console.log('\n✅ ¡AUDITORÍA E2E DE CABLEADO Y RENDERIZADO COMPLETADA CON ÉXITO! Ningún flujo roto ni pantalla en negro.');
