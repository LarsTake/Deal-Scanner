import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// MV3 content scripts are classic scripts: inline every dependency into one IIFE.
export default defineConfig({
  publicDir: false,
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    lib: { entry: resolve(__dirname, 'src/content.ts'), name: 'DealScannerContent', formats: ['iife'], fileName: () => 'content.js' },
  },
});
