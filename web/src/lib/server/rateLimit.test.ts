import { describe, expect, it } from 'vitest';
import { combinedRateLimitResponse, rateLimitResponse } from './rateLimit';

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
