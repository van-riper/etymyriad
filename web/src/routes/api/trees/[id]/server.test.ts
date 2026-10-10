import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { getSql } from '$lib/server/db';

describe('GET /api/trees/:id', () => {
  it('returns a bounded ancestor/descendant slice for a real id', async () => {
    const sql = await getSql();
    const [row] = (await sql`
      SELECT t.id FROM term t JOIN language l ON l.id = t.language_id
      WHERE l.code = 'la' AND t.headword = 'etymologia'
      LIMIT 1
    `) as Array<{ id: number }>;
    expect(row).toBeDefined();

    const response = await GET({
      params: { id: String(row.id) },
      url: new URL('http://x'),
    } as Parameters<typeof GET>[0]);

    const body = (await response.json()) as {
      focusId: number;
      nodes: Array<{ id: number; depth: number }>;
      edges: unknown[];
    };
    expect(body.focusId).toBe(row.id);
    expect(body.nodes.some((n) => n.depth === 0)).toBe(true);
    expect(Array.isArray(body.edges)).toBe(true);
  });

  it('404s for an id that does not exist', async () => {
    await expect(
      GET({
        params: { id: '2147483647' },
        url: new URL('http://x'),
      } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({
      status: 404,
      body: { message: expect.any(String) },
    });
  });

  it('404s a non-integer id', async () => {
    await expect(
      GET({ params: { id: 'abc' }, url: new URL('http://x') } as never),
    ).rejects.toMatchObject({ status: 404 });
  });

  it('400s a malformed section', async () => {
    await expect(
      GET({
        params: { id: '1' },
        url: new URL('http://x?section=two'),
      } as never),
    ).rejects.toMatchObject({ status: 400 });
  });
});
