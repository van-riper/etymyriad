import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: 'server',
          environment: 'node',
          exclude: ['src/**/*.svelte.test.ts'],
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
