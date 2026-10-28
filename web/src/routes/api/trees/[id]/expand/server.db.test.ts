import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { getSql } from '$lib/server/db';

describe('GET /api/trees/:id/expand', () => {
  async function idFor(langCode: string, headword: string): Promise<number> {
    const sql = await getSql();
    const [row] = (await sql`
      SELECT t.id FROM term t JOIN language l ON l.id = t.language_id
      WHERE l.code = ${langCode} AND t.headword = ${headword}
      LIMIT 1
    `) as Array<{ id: number }>;
    expect(row).toBeDefined();
    return row.id;
  }

  function req(
    id: string | number,
    qs: Record<string, string>,
  ): Parameters<typeof GET>[0] {
    return {
      params: { id: String(id) },
      url: new URL(
        `http://localhost/api/trees/${id}/expand?${new URLSearchParams(qs)}`,
      ),
    } as Parameters<typeof GET>[0];
  }

  it('returns the next batch beyond an overflowed real parent', async () => {
    const focusId = await idFor('en', '-ly');

    const response = await GET(req(focusId, { dir: 'descendant', depth: '0' }));
    const body = (await response.json()) as {
      nodes: Array<{ id: number }>;
      edges: unknown[];
      overflow: Array<{ parentId: number; count: number }>;
    };

    expect(body.nodes.length).toBeGreaterThan(0);
    expect(Array.isArray(body.edges)).toBe(true);
    expect(body.overflow.some((o) => o.parentId === focusId)).toBe(true);
  });

  it('excludes ids passed via the exclude param', async () => {
    const focusId = await idFor('en', '-ly');
    const first = (await (
      await GET(req(focusId, { dir: 'descendant', depth: '0' }))
    ).json()) as { nodes: Array<{ id: number }> };
    const knownIds = first.nodes.map((n) => n.id);

    const second = await GET(
      req(focusId, {
        dir: 'descendant',
        depth: '0',
        exclude: knownIds.join(','),
      }),
    );
    const body = (await second.json()) as { nodes: Array<{ id: number }> };

    for (const node of body.nodes) {
      expect(knownIds).not.toContain(node.id);
    }
  });

  it('404s for an id that does not exist', async () => {
    await expect(
      GET(
        req('2147483647', {
          dir: 'descendant',
          depth: '0',
        }),
      ),
    ).rejects.toMatchObject({
      status: 404,
      body: { message: expect.any(String) },
    });
  });

  it('404s for a non-integer id, not a 500', async () => {
    await expect(
      GET(req('abc', { dir: 'descendant', depth: '0' })),
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

  it.each(['101', '-101', '99999999999'])(
    '400s for a depth outside the walk limit (%s), not a 500',
    async (depth) => {
      const focusId = await idFor('en', '-ly');
      await expect(
        GET(req(focusId, { dir: 'descendant', depth })),
      ).rejects.toMatchObject({
        status: 400,
        body: { message: expect.any(String) },
      });
    },
  );

  it('400s for an invalid section', async () => {
    const focusId = await idFor('en', '-ly');
    await expect(
      GET(req(focusId, { dir: 'descendant', depth: '0', section: 'x' })),
    ).rejects.toMatchObject({
      status: 400,
      body: { message: expect.any(String) },
    });
  });

  it('rejects a non-integer exclude id', async () => {
    const url = new URL('http://x?dir=ancestor&depth=-1&exclude=1,abc');
    await expect(
      GET({ params: { id: '1' }, url } as never),
    ).rejects.toMatchObject({ status: 400 });
  });

  it('lets the edge cache the batch until the next reload', async () => {
    const focusId = await idFor('en', '-ly');

    const response = await GET(req(focusId, { dir: 'descendant', depth: '0' }));

    expect(response.headers.get('cache-control')).toBe(
      'public, s-maxage=86400',
    );
  });
});
