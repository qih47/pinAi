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
});