import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defaultExclude, defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: 'server',
          environment: 'node',
          exclude: [...defaultExclude, 'src/**/*.svelte.test.ts', 'e2e/**'],
          // Real Postgres queries against the multi-million-row local
          // dataset (e.g. randomLexeme's full-table scan) can run past
          // vitest's 5s default under concurrent test load.
          testTimeout: 15000,
        },
      },
      {
        extends: true,
        plugins: [svelteTesting()],
        test: {
          name: 'client',
          environment: 'jsdom',
          include: ['src/**/*.svelte.test.ts'],
          setupFiles: ['./src/vitest-setup-client.ts'],
        },
      },
    ],
  },
});
