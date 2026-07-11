import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Renderer (React) lives in src/ and is served by Vite on port 5173 in dev.
// `base: './'` makes the production build use relative asset paths so Electron
// can load it from the local filesystem via file://.
export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      ignored: ['**/engine/**'],
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
