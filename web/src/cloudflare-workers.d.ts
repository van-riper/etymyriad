declare module 'cloudflare:workers' {
  interface RateLimiter {
    limit(options: { key: string }): Promise<{ success: boolean }>;
  }

  export const env: {
    RL_API: RateLimiter;
    RL_GLOBAL: RateLimiter;
  };

  export function waitUntil(promise: Promise<unknown>): void;
}

interface CacheStorage {
  readonly default: Cache;
}
