import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { decodeViewportTile } from '$lib/binaryTile';

describe('GET /api/viewport', () => {
  it('returns 400 when the bounding box is missing', async () => {
    const url = new URL('http://localhost/api/viewport');
    await expect(
      GET({ url } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({ status: 400 });
  });

  it('returns 400 when only part of the bounding box is given', async () => {
    const url = new URL('http://localhost/api/viewport?minX=0&minY=0');
    await expect(
      GET({ url } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({ status: 400 });
  });

  it('returns a binary tile for a viewport-sized bounding box', async () => {
    // A moderate box, not one spanning the whole coordinate range: the
    // real DrL layout only spans roughly ±1100, so a box "generously
    // large" enough to look safe can accidentally request the entire
    // 2M-row graph in one call -- exactly the whole-table fetch this
    // feature exists to avoid. A real caller (a browser viewport) never
    // asks for that either.
    const url = new URL(
      'http://localhost/api/viewport?minX=-10&minY=-10&maxX=10&maxY=10',
    );
    const response = await GET({ url } as Parameters<typeof GET>[0]);
    expect(response.headers.get('content-type')).toBe(
      'application/octet-stream',
    );
    const tile = decodeViewportTile(await response.arrayBuffer());
    expect(Array.isArray(tile.nodes)).toBe(true);
    expect(Array.isArray(tile.edges)).toBe(true);
  });
});
