import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiProxyTarget = process.env.VITE_BLACKBOX_API_PROXY || process.env.VITE_BLACKBOX_API_BASE || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: apiProxyTarget, changeOrigin: true, ws: true },
      '/healthz': { target: apiProxyTarget, changeOrigin: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts', 'echarts-for-react'],
          vendor: ['react', 'react-dom', 'lucide-react'],
        },
      },
    },
  },
});
