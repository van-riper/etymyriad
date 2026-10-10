import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { getSql } from '$lib/server/db';

describe('GET /api/terms/:id', () => {
  it('returns term detail for a real id', async () => {
    const sql = await getSql();
    const [row] = (await sql`
      SELECT t.id FROM term t JOIN language l ON l.id = t.language_id
      WHERE l.code = 'en' AND t.headword = 'etymology'
      LIMIT 1
    `) as Array<{ id: number }>;
    expect(row).toBeDefined();

    const response = await GET({
      params: { id: String(row.id) },
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
      GET({ params: { id: '2147483647' } } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({
      status: 404,
      body: { message: expect.any(String) },
    });
  });

  it('404s for a non-integer id, not a 500', async () => {
    await expect(
      GET({ params: { id: 'abc' } } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({
      status: 404,
      body: { message: expect.any(String) },
    });
  });
});
