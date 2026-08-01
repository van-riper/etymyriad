import { describe, expect, it } from 'vitest';
import {
  decodeViewportTile,
  decodeViewportTileToGraph,
  encodeViewportTile,
} from './binaryTile';
import { buildGraph } from './graph';
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

describe('decodeViewportTileToGraph', () => {
  // The whole-graph route decodes straight to cosmos.gl's typed
  // arrays (ETYM-108), skipping the per-node/per-edge object arrays
  // decodeViewportTile+buildGraph build for the focused-word route.
  // Both paths must agree on the same input.
  it('matches decodeViewportTile + buildGraph for the same buffer', () => {
    const buffer = encodeViewportTile(SAMPLE);
    const expected = buildGraph(decodeViewportTile(buffer), SAMPLE.nodes[1].id, 'dark');

    const actual = decodeViewportTileToGraph(buffer, SAMPLE.nodes[1].id, 'dark');

    expect(actual.ids).toEqual(expected.ids);
    expect(Array.from(actual.positions)).toEqual(Array.from(expected.positions));
    expect(Array.from(actual.colors)).toEqual(Array.from(expected.colors));
    expect(Array.from(actual.sizes)).toEqual(Array.from(expected.sizes));
    expect(Array.from(actual.links)).toEqual(Array.from(expected.links));
    expect(Array.from(actual.linkColors)).toEqual(Array.from(expected.linkColors));
  });

  it('matches with no focus node and the default (light) theme', () => {
    const buffer = encodeViewportTile(SAMPLE);
    const expected = buildGraph(decodeViewportTile(buffer), null);

    const actual = decodeViewportTileToGraph(buffer, null);

    expect(Array.from(actual.colors)).toEqual(Array.from(expected.colors));
    expect(Array.from(actual.sizes)).toEqual(Array.from(expected.sizes));
  });

  it('handles an empty tile', () => {
    const buffer = encodeViewportTile({ nodes: [], edges: [] });
    const graph = decodeViewportTileToGraph(buffer, null);
    expect(graph.ids).toEqual([]);
    expect(graph.positions).toHaveLength(0);
    expect(graph.links).toHaveLength(0);
  });
});
