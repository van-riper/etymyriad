import type { Handle } from '@sveltejs/kit/hooks';
import { env, waitUntil } from 'cloudflare:workers';
import { dev } from '$app/env';
import {
  combinedRateLimitResponse,
  rateLimitKey,
} from '#lib/server/rateLimit.js';

// Caches successful public GET /api/* responses in each Cloudflare
// location, and serves a hit before anything else runs. Skipped in dev.
//
// Rate-limits /api/* so a scraper can't keep Neon's compute awake and
// run up a real bill. Skipped in dev, since local traffic isn't the
// abuse case this guards. A cache hit returns first, so only requests
// that reach the database count.
//
// Two buckets: RL_API caps each client, and RL_GLOBAL caps every
// client together, since per-client limits alone can't bound load from
// many addresses. Cloudflare counts both per location, so RL_GLOBAL
// bounds each location's load, not the whole site's.
export const handle: Handle = async ({ event, resolve }) => {
  const isApi = event.url.pathname.startsWith('/api/');
  const edgeCacheable = !dev && isApi && event.request.method === 'GET';

  if (edgeCacheable) {
    const cached = await caches.default.match(event.request);
    if (cached) {
      return cached;
    }
  }

  if (!dev && isApi) {
    const [perIp, global] = await Promise.all([
      env.RL_API.limit({ key: rateLimitKey(event.getClientAddress()) }),
      env.RL_GLOBAL.limit({ key: 'global' }),
    ]);
    const limited = combinedRateLimitResponse([perIp, global]);
    if (limited) {
      return limited;
    }
  }

  let response = await resolve(event);
  if (isApi) {
    response = await normalizeApiErrorResponse(response);
  }
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('X-Content-Type-Options', 'nosniff');
  if (edgeCacheable && isStorable(response)) {
    waitUntil(caches.default.put(event.request, response.clone()));
  }
  return response;
};

function isStorable(response: Response): boolean {
  const cacheControl = response.headers.get('cache-control') ?? '';
  return (
    response.status === 200 &&
    /\bpublic\b/i.test(cacheControl) &&
    !/(private|no-cache|no-store)/i.test(cacheControl)
  );
}

// Statuses SvelteKit itself can return without going through
// error(): an unmatched route (404) renders the full HTML error
// page, which isn't a usable message even once drained.
const STATUS_MESSAGES: Record<number, string> = {
  404: 'Not Found',
  405: 'Method Not Allowed',
};

// SvelteKit's own fallback responses for an unmatched /api/* route
// (404, HTML) and an unsupported method on a real one (405, plain
// text) don't match the { message } shape every explicit error()
// call already returns, so rewrap them so every /api/* error is JSON.
async function normalizeApiErrorResponse(
  response: Response,
): Promise<Response> {
  const contentType = response.headers.get('content-type') ?? '';
  if (response.status < 400 || contentType.includes('application/json')) {
    return response;
  }
  // Always drain the original body, even when its text isn't the
  // message we use: an un-consumed stream corrupts the next
  // request on the same keep-alive connection.
  const text = (await response.text()).trim();
  const message =
    !contentType.includes('text/html') && text
      ? text
      : (STATUS_MESSAGES[response.status] ?? `HTTP ${response.status}`);
  // Built fresh, not copied from the original response: its
  // Content-Length describes the old (much larger) body, and
  // reusing it would desync the next request on a keep-alive
  // connection. Allow is the one header worth carrying over, since
  // it's meaningful on a 405.
  const headers = new Headers({ 'content-type': 'application/json' });
  const allow = response.headers.get('allow');
  if (allow) headers.set('allow', allow);
  return new Response(JSON.stringify({ message }), {
    status: response.status,
    headers,
  });
}
