import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Plugin sederhana untuk mengarahkan semua route ke analytics.html
// Ini memastikan SPA routing React Router tetap jalan di mode development
const rewriteToAnalyticsPlugin = () => {
  return {
    name: 'rewrite-to-analytics',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        // HANYA rewrite jika ini adalah navigasi browser (Accept: text/html)
        // dan BUKAN request file statis (punya ekstensi file)
        const hasFileExtension = /\.[a-zA-Z0-9]+$/.test(req.url.split('?')[0]);
        const isViteInternal = req.url.startsWith('/@') || req.url.startsWith('/__');
        const isBrowserNav = req.headers['accept']?.includes('text/html') && !hasFileExtension && !isViteInternal;
        
        if (isBrowserNav) {
          req.url = '/analytics.html';
        }
        next();
      });
    }
  };
};

export default defineConfig({
  plugins: [react(), rewriteToAnalyticsPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174,
    host: true,
  },
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'zustand',
      'lucide-react',
      'date-fns',
      'clsx',
      'tailwind-merge',
    ],
  },
});
