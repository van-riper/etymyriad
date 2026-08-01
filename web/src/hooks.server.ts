import type { Handle } from '@sveltejs/kit';
import { dev } from '$app/environment';
import { combinedRateLimitResponse } from '$lib/server/rateLimit';

// Rate-limits /api/* so a scraper can't keep Neon's compute awake and
// run up a real bill. Skipped in dev: `platform` doesn't exist under
// plain `vite dev`, and local traffic isn't the abuse case this guards.
//
// Two buckets: RL_API is a per-IP floor against any single abusive
// client; RL_GLOBAL is a shared site-wide pool, since the resource
// being protected (Neon compute cost) is site-wide, not per-visitor --
// per-IP limiting alone can't bound aggregate load from many distinct
// IPs (see ETYM-101).
export const handle: Handle = async ({ event, resolve }) => {
  if (!dev && event.url.pathname.startsWith('/api/') && event.platform?.env) {
    const { RL_API, RL_GLOBAL } = event.platform.env;
    const [perIp, global] = await Promise.all([
      RL_API.limit({ key: event.getClientAddress() }),
      RL_GLOBAL.limit({ key: 'global' }),
    ]);
    const limited = combinedRateLimitResponse([perIp, global]);
    if (limited) {
      return limited;
    }
  }
  return resolve(event);
};
