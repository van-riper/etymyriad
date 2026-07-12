import { describe, expect, it } from 'vitest';
import { buildGraph } from './graph';
import type { EgoNetwork, Lexeme } from './types';

function lexeme(id: string, headword: string): Lexeme {
  return {
    id,
    langCode: 'en',
    headword,
    etymologyNumber: null,
    romanization: null,
    isReconstructed: false,
    sourceRef: `en:${headword}`,
    senses: [],
  };
}

const RING2_SIZE = 12;
const CROWDED_RING: EgoNetwork = {
  focusId: 'f',
  nodes: [
    lexeme('f', 'focus'),
    lexeme('a', 'ring1'),
    ...Array.from({ length: RING2_SIZE }, (_, i) => lexeme(`b${i}`, `ring2-${i}`)),
  ],
  edges: [
    { srcId: 'a', dstId: 'f', relType: 'inherited', sourceRef: 'en:focus' },
    ...Array.from({ length: RING2_SIZE }, (_, i) => ({
      srcId: `b${i}`,
      dstId: 'a',
      relType: 'inherited' as const,
      sourceRef: 'en:ring1',
    })),
  ],
};

const DENSE_RING_SIZE = 300;
const DENSE_RING: EgoNetwork = {
  focusId: 'f',
  nodes: [
    lexeme('f', 'focus'),
    lexeme('a', 'ring1'),
    ...Array.from({ length: DENSE_RING_SIZE }, (_, i) =>
      lexeme(`c${i}`, `ring2-${i}`),
    ),
  ],
  edges: [
    { srcId: 'a', dstId: 'f', relType: 'inherited', sourceRef: 'en:focus' },
    ...Array.from({ length: DENSE_RING_SIZE }, (_, i) => ({
      srcId: `c${i}`,
      dstId: 'a',
      relType: 'inherited' as const,
      sourceRef: 'en:ring1',
    })),
  ],
};

// Mirrors a real dense word like "water", where both hop-1 and hop-2
// are themselves crowded, not just hop-2 -- this is what actually
// produces the empty-gap-near-the-focus look, since sqrt(count) alone
// pushes both rings out by a similar amount.
const RING1_DENSE_SIZE = 150;
const RING2_DENSE_SIZE = 500;
const BOTH_RINGS_DENSE: EgoNetwork = {
  focusId: 'f',
  nodes: [
    lexeme('f', 'focus'),
    ...Array.from({ length: RING1_DENSE_SIZE }, (_, i) =>
      lexeme(`r1_${i}`, `ring1-${i}`),
    ),
    ...Array.from({ length: RING2_DENSE_SIZE }, (_, i) =>
      lexeme(`r2_${i}`, `ring2-${i}`),
    ),
  ],
  edges: [
    ...Array.from({ length: RING1_DENSE_SIZE }, (_, i) => ({
      srcId: `r1_${i}`,
      dstId: 'f',
      relType: 'inherited' as const,
      sourceRef: 'en:focus',
    })),
    ...Array.from({ length: RING2_DENSE_SIZE }, (_, i) => ({
      srcId: `r2_${i}`,
      dstId: 'r1_0',
      relType: 'inherited' as const,
      sourceRef: 'en:ring1',
    })),
  ],
};

const WATER_CHAIN: EgoNetwork = {
  focusId: '1',
  nodes: [
    {
      id: '1',
      langCode: 'en',
      headword: 'water',
      etymologyNumber: null,
      romanization: null,
      isReconstructed: false,
      sourceRef: 'en:water',
      senses: [],
    },
    {
      id: '2',
      langCode: 'gem-pro',
      headword: 'watōr',
      etymologyNumber: null,
      romanization: null,
      isReconstructed: true,
      sourceRef: 'gem-pro:watōr',
      senses: [],
    },
    {
      id: '3',
      langCode: 'ine-pro',
      headword: 'wódr̥',
      etymologyNumber: null,
      romanization: null,
      isReconstructed: true,
      sourceRef: 'ine-pro:wódr̥',
      senses: [],
    },
  ],
  edges: [
    { srcId: '2', dstId: '1', relType: 'inherited', sourceRef: 'en:water' },
    { srcId: '3', dstId: '2', relType: 'inherited', sourceRef: 'gem-pro:watōr' },
  ],
};

describe('buildGraph', () => {
  it('adds one graph node per lexeme', () => {
    const graph = buildGraph(WATER_CHAIN);
    expect(graph.order).toBe(3);
    expect(graph.hasNode('1')).toBe(true);
    expect(graph.getNodeAttribute('1', 'label')).toContain('water');
  });

  it('adds one graph edge per etymology row', () => {
    const graph = buildGraph(WATER_CHAIN);
    expect(graph.size).toBe(2);
    expect(graph.hasEdge('2', '1')).toBe(true);
    expect(graph.hasEdge('3', '2')).toBe(true);
  });

  it('carries headword and langCode for click-to-navigate', () => {
    const graph = buildGraph(WATER_CHAIN);
    expect(graph.getNodeAttribute('2', 'headword')).toBe('watōr');
    expect(graph.getNodeAttribute('2', 'langCode')).toBe('gem-pro');
  });

  it('marks the focus node distinctly', () => {
    const graph = buildGraph(WATER_CHAIN);
    expect(graph.getNodeAttribute('1', 'color')).not.toBe(
      graph.getNodeAttribute('2', 'color'),
    );
  });

  it('places the focus node at the origin', () => {
    const graph = buildGraph(WATER_CHAIN);
    expect(graph.getNodeAttribute('1', 'x')).toBe(0);
    expect(graph.getNodeAttribute('1', 'y')).toBe(0);
  });

  it('places nodes farther from the focus at a larger radius', () => {
    // node 2 is one hop from the focus (node 1), node 3 is two hops
    // (via node 2) -- radius should grow with hop distance, not just
    // spread everything onto one circle.
    const graph = buildGraph(WATER_CHAIN);
    const radiusOf = (id: string) =>
      Math.hypot(
        graph.getNodeAttribute(id, 'x'),
        graph.getNodeAttribute(id, 'y'),
      );
    expect(radiusOf('2')).toBeGreaterThan(0);
    expect(radiusOf('3')).toBeGreaterThan(radiusOf('2'));
  });

  it('keeps a crowded ring farther out than a sparser nearer one', () => {
    const graph = buildGraph(CROWDED_RING);
    const radiusOf = (id: string) =>
      Math.hypot(
        graph.getNodeAttribute(id, 'x'),
        graph.getNodeAttribute(id, 'y'),
      );
    expect(radiusOf('b0')).toBeGreaterThan(radiusOf('a'));
  });

  it('pushes a dense ring out, but keeps growth compact (sqrt, not linear)', () => {
    // A few hundred nodes should still land close to the focus -- no
    // dead gap between the center and everything else -- while a ring
    // this crowded still needs to sit farther out than a sparse one.
    const graph = buildGraph(DENSE_RING);
    const radiusOf = (id: string) =>
      Math.hypot(
        graph.getNodeAttribute(id, 'x'),
        graph.getNodeAttribute(id, 'y'),
      );
    expect(radiusOf('c0')).toBeGreaterThan(radiusOf('a'));
    expect(radiusOf('c0')).toBeLessThan(15);
  });

  it('gives same-ring nodes slightly different radii instead of a perfect circle', () => {
    // Deterministic per-node jitter, not a shared ring radius -- avoids
    // the "too structured" look of every node landing on one exact
    // circle.
    const graph = buildGraph(CROWDED_RING);
    const radiusOf = (id: string) =>
      Math.hypot(
        graph.getNodeAttribute(id, 'x'),
        graph.getNodeAttribute(id, 'y'),
      );
    expect(Math.abs(radiusOf('b0') - radiusOf('b1'))).toBeGreaterThan(0.1);
  });

  it('pulls a crowded near ring in close, even when a farther ring is also crowded', () => {
    // The empty-gap-near-the-focus complaint happens when ring 1 is
    // itself dense: sqrt(count) alone still pushes it out almost as
    // far as ring 2. Ring radius should compress toward the focus
    // relative to the outermost ring, not just track each ring's own
    // node count in isolation.
    const graph = buildGraph(BOTH_RINGS_DENSE);
    const radiusOf = (id: string) =>
      Math.hypot(
        graph.getNodeAttribute(id, 'x'),
        graph.getNodeAttribute(id, 'y'),
      );
    const ring1Radius = radiusOf('r1_1');
    const ring2Radius = radiusOf('r2_0');
    expect(ring1Radius).toBeGreaterThan(0);
    expect(ring1Radius / ring2Radius).toBeLessThan(0.4);
  });

  it('lays out the same network identically across calls', () => {
    // Jitter must be seeded from the node id, not Math.random(), so a
    // node doesn't jump to a new position every time the same
    // ego-network is rendered.
    const first = buildGraph(CROWDED_RING);
    const second = buildGraph(CROWDED_RING);
    expect(first.getNodeAttribute('b3', 'x')).toBe(
      second.getNodeAttribute('b3', 'x'),
    );
    expect(first.getNodeAttribute('b3', 'y')).toBe(
      second.getNodeAttribute('b3', 'y'),
    );
  });

  it('keeps both edges when one pair has more than one rel_type', () => {
    // Real data does this: the same two lexemes can be linked by both a
    // "derived" and a "cognate" row, which is two separate DB rows since
    // the unique key includes rel_type.
    const network: EgoNetwork = {
      ...WATER_CHAIN,
      edges: [
        ...WATER_CHAIN.edges,
        { srcId: '2', dstId: '1', relType: 'cognate', sourceRef: 'en:water' },
      ],
    };

    const graph = buildGraph(network);
    expect(graph.size).toBe(3);
  });
});
