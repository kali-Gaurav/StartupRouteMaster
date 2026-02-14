import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// image optimization: postbuild script runs `scripts/convert-images.cjs` to produce WebP versions
// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
});
2
