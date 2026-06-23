import js from '@eslint/js';
import ts from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import prettier from 'eslint-config-prettier';
import globals from 'globals';
import svelteConfig from './svelte.config.js';

// Flat config. Layering: ESLint core rules, then typescript-eslint for TS,
// then eslint-plugin-svelte for .svelte. The two prettier configs come last
// and disable any rule that would fight the Prettier formatter (see
// .prettierrc.json). House rules below mirror the typescript-svelte-style skill.
export default ts.config(
  { ignores: ['.svelte-kit/', 'build/', '.wrangler/'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs.recommended,
  prettier,
  ...svelte.configs.prettier,
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    // .svelte files carry <script lang="ts">, so hand the TS parser to the
    // svelte parser and let it read svelte.config.js (runes, preprocessors).
    files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
    languageOptions: {
      parserOptions: {
        parser: ts.parser,
        extraFileExtensions: ['.svelte'],
        svelteConfig,
      },
    },
  },
  {
    // House rules: no `any`, strict equality, no `var`.
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      eqeqeq: ['error', 'always', { null: 'ignore' }],
      'no-var': 'error',
    },
  },
);
