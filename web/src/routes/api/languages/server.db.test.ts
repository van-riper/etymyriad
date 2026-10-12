import { describe, expect, it } from 'vitest';
import { GET } from './+server';

describe('GET /api/languages', () => {
  it('returns every language as {code, name}, no alias-comma codes', async () => {
    const response = await GET({} as Parameters<typeof GET>[0]);
    const body = (await response.json()) as Array<{
      code: string;
      name: string;
    }>;

    expect(body.length).toBeGreaterThan(100);
    expect(body.some((l) => l.code === 'en' && l.name === 'English')).toBe(
      true,
    );
    expect(body.every((l) => !l.code.includes(','))).toBe(true);
  });
});
