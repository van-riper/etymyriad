import { describe, expect, it } from 'vitest';
import { GET } from './+server';

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

  it('returns tile JSON when the full bounding box is given', async () => {
    const url = new URL(
      'http://localhost/api/viewport?minX=-1000000&minY=-1000000&maxX=1000000&maxY=1000000',
    );
    const response = await GET({ url } as Parameters<typeof GET>[0]);
    const body = (await response.json()) as {
      nodes: unknown[];
      edges: unknown[];
    };
    expect(Array.isArray(body.nodes)).toBe(true);
    expect(Array.isArray(body.edges)).toBe(true);
  });
});
