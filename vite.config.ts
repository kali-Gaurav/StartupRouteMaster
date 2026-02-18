import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// image optimization: postbuild script runs `scripts/convert-images.cjs` to produce WebP versions
// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
});
2
