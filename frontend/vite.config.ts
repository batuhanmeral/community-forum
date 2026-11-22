import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // The SPA opens its socket on its own origin; in dev that is this server.
    proxy: {
      '/ws': { target: 'ws://localhost:8001', ws: true },
    },
  },
});
