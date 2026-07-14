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
