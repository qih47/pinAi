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
        // Jika request bukan untuk file statis atau assets
        if (!req.url.includes('.') || req.url.includes('/analytics')) {
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
  build: {
    target: 'esnext',
    minify: 'esbuild',
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'analytics.html'),
      }
    }
  },
});
