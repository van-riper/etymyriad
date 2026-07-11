import { describe, expect, it } from 'vitest';
import { buildGraph } from './graph';
import type { EgoNetwork } from './types';

const WATER_CHAIN: EgoNetwork = {
  focusId: 1,
  nodes: [
    {
      id: 1,
      langCode: 'en',
      headword: 'water',
      gloss: null,
      romanization: null,
      pos: null,
      isReconstructed: false,
      sourceRef: 'en:water',
    },
    {
      id: 2,
      langCode: 'gem-pro',
      headword: 'watōr',
      gloss: null,
      romanization: null,
      pos: null,
      isReconstructed: true,
      sourceRef: 'gem-pro:watōr',
    },
    {
      id: 3,
      langCode: 'ine-pro',
      headword: 'wódr̥',
      gloss: null,
      romanization: null,
      pos: null,
      isReconstructed: true,
      sourceRef: 'ine-pro:wódr̥',
    },
  ],
  edges: [
    { srcId: 2, dstId: 1, relType: 'inherited', sourceRef: 'en:water' },
    { srcId: 3, dstId: 2, relType: 'inherited', sourceRef: 'gem-pro:watōr' },
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

  it('marks the focus node distinctly', () => {
    const graph = buildGraph(WATER_CHAIN);
    expect(graph.getNodeAttribute('1', 'color')).not.toBe(
      graph.getNodeAttribute('2', 'color'),
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
        { srcId: 2, dstId: 1, relType: 'cognate', sourceRef: 'en:water' },
      ],
    };

    const graph = buildGraph(network);
    expect(graph.size).toBe(3);
  });
});
