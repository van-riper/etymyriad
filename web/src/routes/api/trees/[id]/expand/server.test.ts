import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { getSql } from '$lib/server/db';

describe('GET /api/trees/:id/expand', () => {
  async function idFor(langCode: string, headword: string): Promise<string> {
    const sql = await getSql();
    const [row] = (await sql`
      SELECT id FROM lexeme
      WHERE lang_code = ${langCode} AND headword = ${headword}
      LIMIT 1
    `) as Array<{ id: string }>;
    expect(row).toBeDefined();
    return row.id;
  }

  function req(
    id: string,
    qs: Record<string, string>,
  ): Parameters<typeof GET>[0] {
    return {
      params: { id },
      url: new URL(
        `http://localhost/api/trees/${id}/expand?${new URLSearchParams(qs)}`,
      ),
    } as Parameters<typeof GET>[0];
  }

  it('returns the next batch beyond an overflowed real parent', async () => {
    const focusId = await idFor('en', '-ly');

    const response = await GET(req(focusId, { dir: 'descendant', depth: '0' }));
    const body = (await response.json()) as {
      nodes: Array<{ id: string }>;
      edges: unknown[];
      overflow: Array<{ parentId: string; count: number }>;
    };

    expect(body.nodes.length).toBeGreaterThan(0);
    expect(Array.isArray(body.edges)).toBe(true);
    expect(body.overflow.some((o) => o.parentId === focusId)).toBe(true);
  });

  it('excludes ids passed via the exclude param', async () => {
    const focusId = await idFor('en', '-ly');
    const first = (await (
      await GET(req(focusId, { dir: 'descendant', depth: '0' }))
    ).json()) as { nodes: Array<{ id: string }> };
    const knownIds = first.nodes.map((n) => n.id);

    const second = await GET(
      req(focusId, {
        dir: 'descendant',
        depth: '0',
        exclude: knownIds.join(','),
      }),
    );
    const body = (await second.json()) as { nodes: Array<{ id: string }> };

    for (const node of body.nodes) {
      expect(knownIds).not.toContain(node.id);
    }
  });

  it('404s for an id that does not exist', async () => {
    await expect(
      GET(
        req('00000000-0000-0000-0000-000000000000', {
          dir: 'descendant',
          depth: '0',
        }),
      ),
    ).rejects.toMatchObject({
      status: 404,
      body: { message: expect.any(String) },
    });
  });

  it('404s for a malformed (non-UUID) id, not a 500', async () => {
    await expect(
      GET(req('not-a-uuid', { dir: 'descendant', depth: '0' })),
    ).rejects.toMatchObject({
      status: 404,
      body: { message: expect.any(String) },
    });
  });

  it('400s for a missing or invalid dir', async () => {
    const focusId = await idFor('en', '-ly');
    await expect(
      GET(req(focusId, { dir: 'sideways', depth: '0' })),
    ).rejects.toMatchObject({
      status: 400,
      body: { message: expect.any(String) },
    });
  });

  it('400s for a non-integer depth', async () => {
    const focusId = await idFor('en', '-ly');
    await expect(
      GET(req(focusId, { dir: 'descendant', depth: 'abc' })),
    ).rejects.toMatchObject({
      status: 400,
      body: { message: expect.any(String) },
    });
  });
});
