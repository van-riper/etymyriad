import adapter from '@sveltejs/adapter-cloudflare';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    // Deploys to Cloudflare Pages; server routes run as Pages Functions.
    adapter: adapter(),
    csp: {
      mode: 'auto',
      directives: {
        'default-src': ['self'],
        // 'unsafe-inline' covers third-party libs (e.g. svelte-sonner)
        // setting inline style attributes at runtime, which can't
        // carry a server-issued nonce.
        'style-src': ['self', 'unsafe-inline', 'https://fonts.googleapis.com'],
        'font-src': ['self', 'https://fonts.gstatic.com'],
        'frame-ancestors': ['none'],
      },
    },
  },
};

export default config;
