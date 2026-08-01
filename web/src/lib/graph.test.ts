import { describe, expect, it } from 'vitest';
import { buildGraph, canvasColors } from './graph';
import type { ViewportTile } from './types';

const TILE: ViewportTile = {
  nodes: [
    { id: '1', x: 0, y: 0, degree: 3 },
    { id: '2', x: 10, y: 5, degree: 1 },
    { id: '3', x: -8, y: 12, degree: 2 },
  ],
  edges: [
    { srcId: '2', dstId: '1', relType: 'derived' },
    { srcId: '3', dstId: '2', relType: 'borrowed' },
  ],
};

describe('buildGraph', () => {
  it('assigns one index per tile node, at its server-given position', () => {
    const graph = buildGraph(TILE, '1');
    expect(graph.ids).toEqual(['1', '2', '3']);
    expect(graph.positions[2]).toBe(10); // node '2' x
    expect(graph.positions[3]).toBe(5); // node '2' y
  });

  it('encodes one link per tile edge, as index pairs', () => {
    const graph = buildGraph(TILE, '1');
    expect(graph.links).toHaveLength(4);
    expect(graph.links[0]).toBe(1); // '2' -> index 1
    expect(graph.links[1]).toBe(0); // '1' -> index 0
    expect(graph.links[2]).toBe(2); // '3' -> index 2
    expect(graph.links[3]).toBe(1); // '2' -> index 1
  });

  it('marks the focus node with a distinct color and larger size', () => {
    const graph = buildGraph(TILE, '1');
    const focusColor = Array.from(graph.colors.slice(0, 4));
    const otherColor = Array.from(graph.colors.slice(4, 8));
    expect(focusColor).not.toEqual(otherColor);
    expect(graph.sizes[0]).toBeGreaterThan(graph.sizes[1]);
  });

  it('keeps both links when one pair has more than one rel_type', () => {
    // Real data does this: the same two lexemes can be linked by both
    // a "derived" and a "cognate" row, since the unique key includes
    // rel_type.
    const tile: ViewportTile = {
      ...TILE,
      edges: [...TILE.edges, { srcId: '2', dstId: '1', relType: 'cognate' }],
    };
    const graph = buildGraph(tile, '1');
    expect(graph.links).toHaveLength(6);
  });

  it('gives every node the plain color/size when there is no focus node', () => {
    const graph = buildGraph(TILE, null);
    const colors = [0, 1, 2].map((i) =>
      Array.from(graph.colors.slice(i * 4, i * 4 + 4)),
    );
    expect(colors[0]).toEqual(colors[1]);
    expect(colors[1]).toEqual(colors[2]);
    expect(graph.sizes[0]).toBe(graph.sizes[1]);
    expect(graph.sizes[1]).toBe(graph.sizes[2]);
  });
});

describe('theme-aware colors', () => {
  it('defaults to light theme colors', () => {
    const graph = buildGraph(TILE, '1');
    expect(graph.colors[0]).toBeCloseTo(175 / 255, 5); // #af3029 red
    expect(graph.colors[1]).toBeCloseTo(48 / 255, 5); // green
    expect(graph.colors[2]).toBeCloseTo(41 / 255, 5); // blue
    expect(graph.colors[3]).toBe(1); // alpha
  });

  it('picks dark-theme node colors', () => {
    const graph = buildGraph(TILE, '1', 'dark');
    expect(graph.colors[0]).toBeCloseTo(209 / 255, 5); // #d14d41 red
    expect(graph.colors[1]).toBeCloseTo(77 / 255, 5); // green
    expect(graph.colors[2]).toBeCloseTo(65 / 255, 5); // blue
  });

  it('exposes matching edge/background colors per theme', () => {
    expect(canvasColors('light').edge).toBe('#b7b5ac');
    expect(canvasColors('dark').edge).toBe('#575653');
    expect(canvasColors('light').bg).toBe('#fffcf0');
    expect(canvasColors('dark').bg).toBe('#100f0f');
  });
});
