import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path'; // 🔥 Tarik utilitas path bawaan Node

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 🔥 Ajari Vite kalau '@' itu adalah folder 'src' secara absolut
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
  },
  build: {
    target: 'esnext',
    minify: 'esbuild',
    chunkSizeWarningLimit: 3000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;

          // ⚠️ ORDER MATTERS: lebih spesifik harus lebih dulu
          // 1. Isolasi react core terlebih dahulu (termasuk semua subpath-nya)
          if (
            id.includes('/node_modules/react/') ||
            id.includes('/node_modules/react-dom/') ||
            id.includes('/node_modules/react-router/') ||
            id.includes('/node_modules/react-router-dom/') ||
            id.includes('/node_modules/scheduler/')
          ) {
            return 'vendor-react';
          }

          // 2. Zustand State Management (berdiri sendiri, tidak tergantung react chunk)
          if (id.includes('/node_modules/zustand/')) {
            return 'vendor-state';
          }

          // 3. Icons
          if (id.includes('/node_modules/lucide-react/')) {
            return 'vendor-icons';
          }

          // 4. PDF viewer (berat, lazy load)
          if (id.includes('/node_modules/pdfjs-dist/') || id.includes('/node_modules/react-pdf/')) {
            return 'vendor-pdf';
          }

          // 5. Markdown/Mermaid/Viewer — gabung ke vendor-core karena saling
          //    bergantung (circular) dengan shared helpers dari core packages.
          //    Pemisahan lebih jauh hanya akan memicu circular chunk warning Rollup.

          // 6. Utilities (axios, animasi)
          if (
            id.includes('/node_modules/axios/') ||
            id.includes('/node_modules/framer-motion/') ||
            id.includes('/node_modules/date-fns/')
          ) {
            return 'vendor-utils';
          }

          // 7. Semua package node_modules sisanya
          return 'vendor-core';
        },
      },
    },
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'lucide-react'],
  },
});