import { defineConfig } from 'vite';
import { resolve } from 'node:path';

export default defineConfig({
  test: {
    environmentOptions: { jsdom: { url: 'https://www.kleinanzeigen.de/' } },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        background: resolve(__dirname, 'src/background.ts'),
        content: resolve(__dirname, 'src/content.ts'),
        popup: resolve(__dirname, 'popup.html'),
      },
      output: { entryFileNames: '[name].js', chunkFileNames: 'chunks/[name]-[hash].js' },
    },
  },
});
