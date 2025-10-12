import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  define: {
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
