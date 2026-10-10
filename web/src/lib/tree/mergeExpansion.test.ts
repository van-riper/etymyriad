import { describe, expect, it } from 'vitest';
import { mergeTreeExpansion } from './mergeExpansion';
import type { TreeSlice } from '../shared/types';

function baseSlice(): TreeSlice {
  return {
    focusId: 1,
    nodes: [
      {
        id: 1,
        langCode: 'en',
        headword: 'focus',
        isReconstructed: false,
        isRedlink: false,
        depth: 0,
      },
      {
        id: 2,
        langCode: 'en',
        headword: 'a1',
        isReconstructed: false,
        isRedlink: false,
        depth: 1,
      },
    ],
    edges: [{ srcId: 1, dstId: 2, relType: 'derived', sourceRef: 'r1' }],
    overflow: [{ parentId: 1, direction: 'descendant', count: 20 }],
  };
}

describe('mergeTreeExpansion', () => {
  it('appends new nodes and edges', () => {
    const merged = mergeTreeExpansion(baseSlice(), 1, 'descendant', {
      nodes: [
        {
          id: 3,
          langCode: 'en',
          headword: 'a2',
          isReconstructed: false,
          isRedlink: false,
          depth: 1,
        },
      ],
      edges: [{ srcId: 1, dstId: 3, relType: 'derived', sourceRef: 'r2' }],
      overflow: [{ parentId: 1, direction: 'descendant', count: 19 }],
    });

    expect(merged.nodes.map((n) => n.id)).toEqual([1, 2, 3]);
    expect(merged.edges).toHaveLength(2);
  });

  it("replaces the expanded parent's overflow count with the server's new value", () => {
    const merged = mergeTreeExpansion(baseSlice(), 1, 'descendant', {
      nodes: [],
      edges: [],
      overflow: [{ parentId: 1, direction: 'descendant', count: 10 }],
    });

    expect(merged.overflow).toEqual([
      { parentId: 1, direction: 'descendant', count: 10 },
    ]);
  });

  it('drops the overflow entry entirely once the server reports none remaining', () => {
    const merged = mergeTreeExpansion(baseSlice(), 1, 'descendant', {
      nodes: [],
      edges: [],
      overflow: [],
    });

    expect(merged.overflow).toEqual([]);
  });

  it("leaves a different parent's overflow entry untouched", () => {
    const slice = baseSlice();
    slice.overflow = [
      ...slice.overflow!,
      { parentId: 2, direction: 'ancestor', count: 3 },
    ];

    const merged = mergeTreeExpansion(slice, 1, 'descendant', {
      nodes: [],
      edges: [],
      overflow: [{ parentId: 1, direction: 'descendant', count: 10 }],
    });

    expect(merged.overflow).toContainEqual({
      parentId: 2,
      direction: 'ancestor',
      count: 3,
    });
  });

  it('adds a new overflow entry for a newly revealed child that is itself over the cap', () => {
    const merged = mergeTreeExpansion(baseSlice(), 1, 'descendant', {
      nodes: [
        {
          id: 3,
          langCode: 'en',
          headword: 'a2',
          isReconstructed: false,
          isRedlink: false,
          depth: 1,
        },
      ],
      edges: [{ srcId: 1, dstId: 3, relType: 'derived', sourceRef: 'r2' }],
      overflow: [
        { parentId: 1, direction: 'descendant', count: 9 },
        { parentId: 3, direction: 'descendant', count: 5 },
      ],
    });

    expect(merged.overflow).toContainEqual({
      parentId: 3,
      direction: 'descendant',
      count: 5,
    });
  });

  it('does not duplicate a node or edge the expansion re-sends', () => {
    const slice = baseSlice();
    const merged = mergeTreeExpansion(slice, 1, 'descendant', {
      nodes: [slice.nodes[1]],
      edges: [slice.edges[0]],
      overflow: [],
    });

    expect(merged.nodes).toHaveLength(2);
    expect(merged.edges).toHaveLength(1);
  });
});
