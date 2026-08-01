import { json } from '@sveltejs/kit';

// Decides the HTTP response for a Cloudflare Rate Limiting binding
// result. Returns null when the request should proceed.
export function rateLimitResponse(result: {
  success: boolean;
}): Response | null {
  if (result.success) {
    return null;
  }
  return json(
    { error: 'rate limited' },
    { status: 429, headers: { 'Retry-After': '60' } },
  );
}

// Combines results from more than one rate limiter (e.g. a per-IP
// bucket and a shared site-wide pool) -- any denial rate-limits the
// request.
export function combinedRateLimitResponse(
  results: Array<{ success: boolean }>,
): Response | null {
  for (const result of results) {
    const response = rateLimitResponse(result);
    if (response) {
      return response;
    }
  }
  return null;
}
