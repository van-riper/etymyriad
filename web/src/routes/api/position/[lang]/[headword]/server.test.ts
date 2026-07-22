import { describe, expect, it } from 'vitest';
import { GET } from './+server';

describe('GET /api/position/:lang/:headword', () => {
  it('returns the position for a real lexeme', async () => {
    const response = await GET({
      params: { lang: 'en', headword: 'etymology' },
    } as Parameters<typeof GET>[0]);

    const body = (await response.json()) as {
      id: string;
      x: number;
      y: number;
    };
    expect(typeof body.id).toBe('string');
    expect(typeof body.x).toBe('number');
    expect(typeof body.y).toBe('number');
  });

  it('404s for a headword that does not exist', async () => {
    await expect(
      GET({
        params: { lang: 'en', headword: 'zzznotaword' },
      } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({ status: 404 });
  });
});
