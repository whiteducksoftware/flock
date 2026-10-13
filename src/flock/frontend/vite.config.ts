import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(version),
    __BUILD_TIMESTAMP__: JSON.stringify(new Date().toISOString()),
    __BUILD_HASH__: JSON.stringify(
      Date.now().toString(36) + Math.random().toString(36).substring(2, 9)
    ),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8344',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8344',
        ws: true,
      },
    },
  },
});
