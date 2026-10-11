import { describe, expect, it } from 'vitest';
import { layoutTree, widthForLabel, NODE_WIDTH } from './index';
import type { TreeSlice } from '../../shared/types';

describe('layoutTree', () => {
  it('positions a lone focus node at the origin', () => {
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
      ],
      edges: [],
    };

    const layout = layoutTree(slice);

    expect(layout.nodes).toHaveLength(1);
    expect(layout.nodes[0]).toMatchObject({
      id: 1,
      x: 0,
      y: 0,
      isFocus: true,
    });
    expect(layout.edges).toHaveLength(0);
    expect(layout.viewBox.width).toBeGreaterThan(0);
    expect(layout.viewBox.height).toBeGreaterThan(0);
  });

  it('lines a linear ancestor chain up left of the focus, one column per generation', () => {
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 2,
          langCode: 'enm',
          headword: 'grandfadre',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 3,
          langCode: 'ang',
          headword: 'ealdefæder',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 2, dstId: 1, relType: 'inherited', sourceRef: 'r1' },
        { srcId: 3, dstId: 2, relType: 'inherited', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get(1)).toMatchObject({ x: 0, y: 0 });
    expect(byId.get(2)!.x).toBeLessThan(0);
    expect(byId.get(3)!.x).toBeLessThan(byId.get(2)!.x);
    expect(byId.get(2)!.y).toBe(byId.get(1)!.y);
    expect(byId.get(3)!.y).toBe(byId.get(1)!.y);

    expect(layout.edges).toHaveLength(2);
  });

  it('mirrors descendants right of the focus, sharing one focus at the origin', () => {
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 2,
          langCode: 'enm',
          headword: 'grandfadre',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 4,
          langCode: 'fr',
          headword: 'grand-père',
          isReconstructed: false,
          isRedlink: false,
          depth: 1,
        },
      ],
      edges: [
        { srcId: 2, dstId: 1, relType: 'inherited', sourceRef: 'r1' },
        { srcId: 1, dstId: 4, relType: 'borrowed', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(layout.nodes.filter((n) => n.id === 1)).toHaveLength(1);
    expect(byId.get(1)).toMatchObject({ x: 0, y: 0 });
    expect(byId.get(2)!.x).toBeLessThan(0);
    expect(byId.get(4)!.x).toBeGreaterThan(0);
  });

  it('drops an edge straddling depth 0, never treating it as a tree edge', () => {
    // a (ancestor, depth -1) and d (descendant, depth 1) are each
    // placed normally by their own real parent edge; a-d straddles
    // the focus and belongs to neither half's filtered edge set, so
    // it places nothing and must not be rendered.
    const slice: TreeSlice = {
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
          id: 5,
          langCode: 'en',
          headword: 'a-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 6,
          langCode: 'en',
          headword: 'd-word',
          isReconstructed: false,
          isRedlink: false,
          depth: 1,
        },
      ],
      edges: [
        { srcId: 5, dstId: 1, relType: 'inherited', sourceRef: 'r1' },
        { srcId: 1, dstId: 6, relType: 'inherited', sourceRef: 'r2' },
        { srcId: 5, dstId: 6, relType: 'mention', sourceRef: 'r3' },
      ],
    };

    const layout = layoutTree(slice);

    expect(layout.edges.some((e) => e.srcId === 5 && e.dstId === 6)).toBe(
      false,
    );
    expect(layout.edges).toHaveLength(2);
  });

  it('scales the viewBox with tree width and depth', () => {
    const narrow: TreeSlice = {
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
          depth: -1,
        },
      ],
      edges: [{ srcId: 2, dstId: 1, relType: 'derived', sourceRef: 'r' }],
    };
    const wide: TreeSlice = {
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
          depth: -1,
        },
        {
          id: 3,
          langCode: 'en',
          headword: 'a2',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 7,
          langCode: 'en',
          headword: 'a3',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 8,
          langCode: 'en',
          headword: 'a4',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 9,
          langCode: 'en',
          headword: 'a5',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [2, 3, 7, 8, 9].map((n) => ({
        srcId: n,
        dstId: 1,
        relType: 'derived' as const,
        sourceRef: `r${n}`,
      })),
    };
    const shallow = narrow;
    const deep: TreeSlice = {
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
          depth: -1,
        },
        {
          id: 3,
          langCode: 'en',
          headword: 'a2',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
        {
          id: 7,
          langCode: 'en',
          headword: 'a3',
          isReconstructed: false,
          isRedlink: false,
          depth: -3,
        },
      ],
      edges: [
        { srcId: 2, dstId: 1, relType: 'derived', sourceRef: 'r1' },
        { srcId: 3, dstId: 2, relType: 'derived', sourceRef: 'r2' },
        { srcId: 7, dstId: 3, relType: 'derived', sourceRef: 'r3' },
      ],
    };

    expect(layoutTree(wide).viewBox.height).toBeGreaterThan(
      layoutTree(narrow).viewBox.height,
    );
    expect(layoutTree(deep).viewBox.width).toBeGreaterThan(
      layoutTree(shallow).viewBox.width,
    );
  });

  it('composes each node label from headword and lang code, sized to fit', () => {
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
      ],
      edges: [],
    };

    const layout = layoutTree(slice);

    expect(layout.nodes[0]).toMatchObject({
      label: 'grandfather (en)',
      width: NODE_WIDTH,
    });
  });

  it('widens a node whose label is longer than the floor width', () => {
    const longHeadword = 'a'.repeat(40);
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
      ],
      edges: [],
    };
    const expectedLabel = `${longHeadword} (en)`;

    const layout = layoutTree(slice);

    expect(layout.nodes[0].label).toBe(expectedLabel);
    expect(layout.nodes[0].width).toBe(widthForLabel(expectedLabel));
    expect(layout.nodes[0].width).toBeGreaterThan(NODE_WIDTH);
  });

  it('tightens the viewBox around a single long-headword focus node', () => {
    const longHeadword = 'a'.repeat(40);
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
      ],
      edges: [],
    };
    const expectedLabel = `${longHeadword} (en)`;

    const layout = layoutTree(slice);

    expect(layout.viewBox.width).toBe(widthForLabel(expectedLabel) + 2 * 16);
  });

  it('keeps adjacent generations from overlapping when a headword is long', () => {
    const longHeadword = 'a'.repeat(40);
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 2,
          langCode: 'en',
          headword: 'short',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 3,
          langCode: 'en',
          headword: 'child',
          isReconstructed: false,
          isRedlink: false,
          depth: 1,
        },
      ],
      edges: [
        { srcId: 2, dstId: 1, relType: 'derived', sourceRef: 'r1' },
        { srcId: 1, dstId: 3, relType: 'derived', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    const focus = byId.get(1)!;
    const ancestor = byId.get(2)!;
    const descendant = byId.get(3)!;

    expect(focus.x - focus.width / 2).toBeGreaterThan(
      ancestor.x + ancestor.width / 2,
    );
    expect(descendant.x - descendant.width / 2).toBeGreaterThan(
      focus.x + focus.width / 2,
    );
  });
});
