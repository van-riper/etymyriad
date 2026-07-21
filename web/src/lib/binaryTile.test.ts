import { describe, expect, it } from 'vitest';
import { decodeViewportTile, encodeViewportTile } from './binaryTile';
import type { ViewportTile } from './types';

const SAMPLE: ViewportTile = {
  nodes: [
    { id: '11111111-1111-1111-1111-111111111111', x: 1.5, y: -2.25, degree: 3 },
    { id: '22222222-2222-2222-2222-222222222222', x: -100.75, y: 0, degree: 0 },
    { id: '33333333-3333-3333-3333-333333333333', x: 42, y: 42, degree: 999 },
  ],
  edges: [
    {
      srcId: '11111111-1111-1111-1111-111111111111',
      dstId: '22222222-2222-2222-2222-222222222222',
      relType: 'inherited',
    },
    {
      srcId: '33333333-3333-3333-3333-333333333333',
      dstId: '11111111-1111-1111-1111-111111111111',
      relType: 'cognate',
    },
  ],
};

describe('encodeViewportTile / decodeViewportTile', () => {
  it('round-trips nodes and edges through an ArrayBuffer', () => {
    const buffer = encodeViewportTile(SAMPLE);
    expect(buffer).toBeInstanceOf(ArrayBuffer);

    const decoded = decodeViewportTile(buffer);
    expect(decoded).toEqual(SAMPLE);
  });

  it('round-trips an empty tile', () => {
    const empty: ViewportTile = { nodes: [], edges: [] };
    const decoded = decodeViewportTile(encodeViewportTile(empty));
    expect(decoded).toEqual(empty);
  });
});
