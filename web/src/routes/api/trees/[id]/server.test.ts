import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { getSql } from '$lib/server/db';

describe('GET /api/trees/:id', () => {
  it('returns a bounded ancestor/descendant slice for a real id', async () => {
    const sql = await getSql();
    const [row] = (await sql`
      SELECT id FROM lexeme
      WHERE lang_code = 'la' AND headword = 'etymologia'
      LIMIT 1
    `) as Array<{ id: string }>;
    expect(row).toBeDefined();

    const response = await GET({
      params: { id: row.id },
    } as Parameters<typeof GET>[0]);

    const body = (await response.json()) as {
      focusId: string;
      nodes: Array<{ id: string; depth: number }>;
      edges: unknown[];
    };
    expect(body.focusId).toBe(row.id);
    expect(body.nodes.some((n) => n.depth === 0)).toBe(true);
    expect(Array.isArray(body.edges)).toBe(true);
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
