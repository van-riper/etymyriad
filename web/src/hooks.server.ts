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
// IPs.
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

  let response = await resolve(event);
  if (event.url.pathname.startsWith('/api/')) {
    response = await normalizeApiErrorResponse(response);
  }
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.headers.set('X-Frame-Options', 'DENY');
  return response;
};

// Statuses SvelteKit itself can return without going through
// error() -- an unmatched route (404) renders the full HTML error
// page, which isn't a usable message even once drained.
const STATUS_MESSAGES: Record<number, string> = {
  404: 'Not Found',
  405: 'Method Not Allowed',
};

// SvelteKit's own fallback responses for an unmatched /api/* route
// (404, HTML) and an unsupported method on a real one (405, plain
// text) don't match the { message } shape every explicit error()
// call already returns -- rewrap them so every /api/* error is JSON.
async function normalizeApiErrorResponse(
  response: Response,
): Promise<Response> {
  const contentType = response.headers.get('content-type') ?? '';
  if (response.status < 400 || contentType.includes('application/json')) {
    return response;
  }
  // Always drain the original body, even when its text isn't the
  // message we use -- an un-consumed stream corrupts the next
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
