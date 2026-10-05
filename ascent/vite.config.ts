import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Relative base so the build works from any GitHub Pages sub-path.
export default defineConfig({
  base: './',
  define: {
    __BUILD__: JSON.stringify(`${(process.env.GITHUB_SHA ?? 'local').slice(0, 7)} · ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC`),
  },
  plugins: [react()],
  build: { outDir: 'dist', sourcemap: false },
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
});
