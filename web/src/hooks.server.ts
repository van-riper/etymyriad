import type { Handle } from '@sveltejs/kit';
import { dev } from '$app/environment';
import { rateLimitResponse } from '$lib/server/rateLimit';

// Rate-limits /api/* so a scraper can't keep Neon's compute awake and
// run up a real bill. Skipped in dev: `platform` doesn't exist under
// plain `vite dev`, and local traffic isn't the abuse case this guards.
export const handle: Handle = async ({ event, resolve }) => {
  if (!dev && event.url.pathname.startsWith('/api/') && event.platform?.env) {
    const result = await event.platform.env.RL_API.limit({
      key: event.getClientAddress(),
    });
    const limited = rateLimitResponse(result);
    if (limited) {
      return limited;
    }
  }
  return resolve(event);
};
