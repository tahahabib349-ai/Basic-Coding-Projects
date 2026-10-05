import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

const BUILD = `${(process.env.GITHUB_SHA ?? 'local').slice(0, 7)} · ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC`;

/** Writes version.json beside the page so an open copy can tell it is out of date. */
const versionFile = { name: 'version-file', generateBundle(this: { emitFile: (f: { type: 'asset'; fileName: string; source: string }) => void }) { this.emitFile({ type: 'asset', fileName: 'version.json', source: JSON.stringify({ build: BUILD }) }); } };

// Relative base so the build works from any GitHub Pages sub-path.
export default defineConfig({
  base: './',
  define: {
    __BUILD__: JSON.stringify(BUILD),
  },
  plugins: [react(), versionFile],
  build: { outDir: 'dist', sourcemap: false },
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
});
