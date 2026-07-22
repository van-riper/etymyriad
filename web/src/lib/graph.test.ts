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
  it('adds one graph node per tile node, at its server-given position', () => {
    const graph = buildGraph(TILE, '1');
    expect(graph.order).toBe(3);
    expect(graph.getNodeAttribute('2', 'x')).toBe(10);
    expect(graph.getNodeAttribute('2', 'y')).toBe(5);
  });

  it('adds one graph edge per tile edge', () => {
    const graph = buildGraph(TILE, '1');
    expect(graph.size).toBe(2);
    expect(graph.hasEdge('2', '1')).toBe(true);
    expect(graph.hasEdge('3', '2')).toBe(true);
  });

  it('marks the focus node with a distinct color and larger size', () => {
    const graph = buildGraph(TILE, '1');
    expect(graph.getNodeAttribute('1', 'color')).not.toBe(
      graph.getNodeAttribute('2', 'color'),
    );
    expect(graph.getNodeAttribute('1', 'size')).toBeGreaterThan(
      graph.getNodeAttribute('2', 'size'),
    );
  });

  it('does not set a label or headword attribute on any node', () => {
    // Tile nodes carry no attribute text (see ETYM-70) -- labels only
    // appear once a hover/click lazily fetches lexeme detail.
    const graph = buildGraph(TILE, '1');
    expect(graph.getNodeAttribute('2', 'label')).toBeUndefined();
    expect(graph.getNodeAttribute('2', 'headword')).toBeUndefined();
  });

  it('keeps both edges when one pair has more than one rel_type', () => {
    // Real data does this: the same two lexemes can be linked by both
    // a "derived" and a "cognate" row, since the unique key includes
    // rel_type.
    const tile: ViewportTile = {
      ...TILE,
      edges: [...TILE.edges, { srcId: '2', dstId: '1', relType: 'cognate' }],
    };
    const graph = buildGraph(tile, '1');
    expect(graph.size).toBe(3);
  });
});

describe('theme-aware colors', () => {
  it('defaults to light theme colors', () => {
    const graph = buildGraph(TILE, '1');
    expect(graph.getNodeAttribute('1', 'color')).toBe('#af3029');
    expect(graph.getNodeAttribute('2', 'color')).toBe('#205ea6');
  });

  it('picks dark-theme node colors', () => {
    const graph = buildGraph(TILE, '1', 'dark');
    expect(graph.getNodeAttribute('1', 'color')).toBe('#d14d41');
    expect(graph.getNodeAttribute('2', 'color')).toBe('#4385be');
  });

  it('exposes matching edge/label colors per theme', () => {
    expect(canvasColors('light').edge).toBe('#b7b5ac');
    expect(canvasColors('dark').edge).toBe('#575653');
  });
});
