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
    { message: 'rate limited' },
    { status: 429, headers: { 'Retry-After': '60' } },
  );
}

// Combines results from more than one rate limiter (e.g. a per-IP
// bucket and a shared site-wide pool): any denial rate-limits the
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

// Keys an IPv6 client on its /64, the block one subscriber usually
// gets, so rotating addresses inside it doesn't buy a fresh bucket.
export function rateLimitKey(address: string): string {
  if (!address.includes(':') || address.includes('.')) {
    return address;
  }
  const [head, tail] = address.split('::');
  const headGroups = head ? head.split(':') : [];
  const tailGroups = tail ? tail.split(':') : [];
  const zeros = Array<string>(8 - headGroups.length - tailGroups.length).fill(
    '0',
  );
  return [...headGroups, ...zeros, ...tailGroups]
    .slice(0, 4)
    .map((group) => parseInt(group, 16).toString(16))
    .join(':');
}
