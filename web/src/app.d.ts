// See https://svelte.dev/docs/kit/types#app.d.ts

declare global {
  namespace App {
    // Cloudflare bindings/secrets are exposed here at runtime.
    interface Platform {
      env?: {
        DATABASE_URL: string;
        RL_API: {
          limit(options: { key: string }): Promise<{ success: boolean }>;
        };
      };
    }
  }
}

export {};
