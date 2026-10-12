/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/** Map a node_modules path to a named vendor chunk (undefined = let Rollup decide). */
function vendorChunk(id: string): string | undefined {
  // Rollup's shared CJS interop helpers: keep them with React (the main CJS consumer) to avoid chunk cycles.
  if (id.includes('commonjsHelpers')) return 'react';
  // Last node_modules segment wins (handles nested deps); normalise Windows separators.
  const matches = [...id.replace(/\\/g, '/').matchAll(/node_modules\/((?:@[^/]+\/)?[^/]+)/g)];
  const pkg = matches.at(-1)?.[1];
  if (!pkg) return undefined;
  if (['react', 'react-dom', 'scheduler', 'react-router', 'react-router-dom', '@remix-run/router'].includes(pkg)) {
    return 'react';
  }
  if (pkg === 'framer-motion' || pkg.startsWith('motion-')) return 'motion';
  if (pkg.startsWith('@chakra-ui/') || pkg.startsWith('@emotion/') || pkg.startsWith('@zag-js/') || pkg.startsWith('@popperjs/')) {
    return 'chakra';
  }
  if (pkg === '@tanstack/react-query' || pkg === '@tanstack/query-core' || pkg === 'axios') return 'query';
  if (
    ['react-markdown', 'unified', 'bail', 'trough', 'vfile', 'vfile-message', 'devlop', 'property-information', 'space-separated-tokens', 'comma-separated-tokens', 'html-url-attributes', 'decode-named-character-reference', 'character-entities', 'estree-util-is-identifier-name', 'style-to-object', 'style-to-js', 'inline-style-parser', 'trim-lines', 'zwitch', 'longest-streak', 'ccount', 'is-plain-obj', 'hast-util-whitespace'].includes(pkg) ||
    /^(remark|rehype|micromark|mdast|hast|unist)-?/.test(pkg)
  ) {
    return 'markdown';
  }
  return undefined;
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    rollupOptions: {
      output: {
        // Stable vendor chunks: cache well across deploys and keep any single chunk small.
        // react-markdown (+ remark/micromark) is only imported by lazy routes, so its chunk
        // is never fetched on the landing page.
        manualChunks: vendorChunk,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    passWithNoTests: true,
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx', 'src/vite-env.d.ts', 'src/**/index.ts'],
      reporter: ['text-summary', 'text'],
    },
  },
});
