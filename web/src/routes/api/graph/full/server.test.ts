import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { decodeViewportTile } from '$lib/binaryTile';
import { getSql } from '$lib/server/db';

describe('GET /api/graph/full', () => {
  it('returns a binary tile covering the whole graph', async () => {
    const sql = await getSql();
    const [{ count: totalNodes }] = (await sql`
      SELECT count(*)::int AS count FROM lexeme_layout
    `) as Array<{ count: number }>;

    const response = await GET({} as Parameters<typeof GET>[0]);

    expect(response.headers.get('content-type')).toBe(
      'application/octet-stream',
    );
    const tile = decodeViewportTile(await response.arrayBuffer());
    expect(tile.nodes.length).toBe(totalNodes);
  }, 600000);
});
