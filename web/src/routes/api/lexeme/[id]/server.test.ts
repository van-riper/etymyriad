import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { lexemePosition } from '$lib/server/queries';

describe('GET /api/lexeme/:id', () => {
  it('returns lexeme detail for a real id', async () => {
    const position = await lexemePosition('en', 'etymology');
    const response = await GET({
      params: { id: position!.id },
    } as Parameters<typeof GET>[0]);

    const body = (await response.json()) as {
      headword: string;
      langCode: string;
      senses: unknown[];
    };
    expect(body.headword).toBe('etymology');
    expect(body.langCode).toBe('en');
    expect(Array.isArray(body.senses)).toBe(true);
  });

  it('404s for an id that does not exist', async () => {
    await expect(
      GET({
        params: { id: '00000000-0000-0000-0000-000000000000' },
      } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({ status: 404 });
  });

  it('404s for a malformed (non-UUID) id, not a 500', async () => {
    await expect(
      GET({
        params: { id: 'not-a-uuid' },
      } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({ status: 404 });
  });
});
