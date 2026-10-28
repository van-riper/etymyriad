import { describe, expect, it } from 'vitest';
import {
  combinedRateLimitResponse,
  rateLimitKey,
  rateLimitResponse,
} from './rateLimit';

describe('rateLimitResponse', () => {
  it('returns null when the limiter allows the request', () => {
    expect(rateLimitResponse({ success: true })).toBeNull();
  });

  it('returns a 429 with Retry-After when the limiter denies the request', async () => {
    const response = rateLimitResponse({ success: false });

    expect(response).not.toBeNull();
    expect(response!.status).toBe(429);
    expect(response!.headers.get('Retry-After')).toBe('60');
    expect(await response!.json()).toEqual({ message: 'rate limited' });
  });
});

describe('combinedRateLimitResponse', () => {
  it('returns null when every limiter allows the request', () => {
    expect(
      combinedRateLimitResponse([{ success: true }, { success: true }]),
    ).toBeNull();
  });

  it('returns a 429 when the per-IP limiter denies the request', () => {
    const response = combinedRateLimitResponse([
      { success: false },
      { success: true },
    ]);

    expect(response).not.toBeNull();
    expect(response!.status).toBe(429);
  });

  it('returns a 429 when the shared global limiter denies the request', () => {
    const response = combinedRateLimitResponse([
      { success: true },
      { success: false },
    ]);

    expect(response).not.toBeNull();
    expect(response!.status).toBe(429);
  });
});

describe('rateLimitKey', () => {
  it('keys an IPv4 client on its full address', () => {
    expect(rateLimitKey('203.0.113.7')).toBe('203.0.113.7');
  });

  it('puts every address in one IPv6 /64 in the same bucket', () => {
    expect(rateLimitKey('2001:db8:1:2:3:4:5:6')).toBe(
      rateLimitKey('2001:db8:1:2:ffff::1'),
    );
  });

  it('expands a compressed prefix and normalizes case and zeros', () => {
    expect(rateLimitKey('2001:DB8:0001::7')).toBe('2001:db8:1:0');
  });

  it('keeps different /64s in different buckets', () => {
    expect(rateLimitKey('2001:db8:1:2::1')).not.toBe(
      rateLimitKey('2001:db8:1:3::1'),
    );
  });

  it('keys an address with an embedded IPv4 part on its full address', () => {
    expect(rateLimitKey('::ffff:203.0.113.7')).toBe('::ffff:203.0.113.7');
  });
});
