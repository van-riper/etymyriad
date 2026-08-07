import { describe, expect, it } from 'vitest';
import { layoutTree, widthForLabel, NODE_WIDTH } from './index';
import type { TreeSlice } from '../../shared/types';

describe('layoutTree', () => {
  it('positions a lone focus node at the origin', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
      ],
      edges: [],
    };

    const layout = layoutTree(slice);

    expect(layout.nodes).toHaveLength(1);
    expect(layout.nodes[0]).toMatchObject({
      id: 'f',
      x: 0,
      y: 0,
      isFocus: true,
    });
    expect(layout.edges).toHaveLength(0);
    expect(layout.viewBox.width).toBeGreaterThan(0);
    expect(layout.viewBox.height).toBeGreaterThan(0);
  });

  it('stacks a linear ancestor chain directly above the focus, one row per generation', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a1',
          langCode: 'enm',
          headword: 'grandfadre',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'a2',
          langCode: 'ang',
          headword: 'ealdefæder',
          isReconstructed: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'a2', dstId: 'a1', relType: 'inherited', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get('f')).toMatchObject({ x: 0, y: 0 });
    expect(byId.get('a1')!.y).toBeLessThan(0);
    expect(byId.get('a2')!.y).toBeLessThan(byId.get('a1')!.y);
    expect(byId.get('a1')!.x).toBe(byId.get('f')!.x);
    expect(byId.get('a2')!.x).toBe(byId.get('f')!.x);

    expect(layout.edges).toHaveLength(2);
    expect(layout.edges.every((e) => e.kind === 'tree')).toBe(true);
  });

  it('mirrors descendants below the focus, sharing one focus at the origin', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a1',
          langCode: 'enm',
          headword: 'grandfadre',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'd1',
          langCode: 'fr',
          headword: 'grand-père',
          isReconstructed: false,
          depth: 1,
        },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'f', dstId: 'd1', relType: 'borrowed', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(layout.nodes.filter((n) => n.id === 'f')).toHaveLength(1);
    expect(byId.get('f')).toMatchObject({ x: 0, y: 0 });
    expect(byId.get('a1')!.y).toBeLessThan(0);
    expect(byId.get('d1')!.y).toBeGreaterThan(0);
  });

  it('marks an edge straddling depth 0 as a cross-link, never the tree default', () => {
    // a (ancestor, depth -1) and d (descendant, depth 1) are each
    // placed normally by their own real parent edge; a-d straddles
    // the focus and belongs to neither half's filtered edge set, so
    // it must not fall through to the 'tree' default.
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a',
          langCode: 'en',
          headword: 'a-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'd',
          langCode: 'en',
          headword: 'd-word',
          isReconstructed: false,
          depth: 1,
        },
      ],
      edges: [
        { srcId: 'a', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'f', dstId: 'd', relType: 'inherited', sourceRef: 'r2' },
        { srcId: 'a', dstId: 'd', relType: 'cognate', sourceRef: 'r3' },
      ],
    };

    const layout = layoutTree(slice);
    const straddling = layout.edges.find(
      (e) => e.srcId === 'a' && e.dstId === 'd',
    );

    expect(straddling?.kind).toBe('cross-link');
  });

  it('scales the viewBox with tree width and depth', () => {
    const narrow: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a1',
          langCode: 'en',
          headword: 'a1',
          isReconstructed: false,
          depth: -1,
        },
      ],
      edges: [{ srcId: 'a1', dstId: 'f', relType: 'derived', sourceRef: 'r' }],
    };
    const wide: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a1',
          langCode: 'en',
          headword: 'a1',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'a2',
          langCode: 'en',
          headword: 'a2',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'a3',
          langCode: 'en',
          headword: 'a3',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'a4',
          langCode: 'en',
          headword: 'a4',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'a5',
          langCode: 'en',
          headword: 'a5',
          isReconstructed: false,
          depth: -1,
        },
      ],
      edges: [1, 2, 3, 4, 5].map((n) => ({
        srcId: `a${n}`,
        dstId: 'f',
        relType: 'derived' as const,
        sourceRef: `r${n}`,
      })),
    };
    const shallow = narrow;
    const deep: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a1',
          langCode: 'en',
          headword: 'a1',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'a2',
          langCode: 'en',
          headword: 'a2',
          isReconstructed: false,
          depth: -2,
        },
        {
          id: 'a3',
          langCode: 'en',
          headword: 'a3',
          isReconstructed: false,
          depth: -3,
        },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'a2', dstId: 'a1', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'a3', dstId: 'a2', relType: 'derived', sourceRef: 'r3' },
      ],
    };

    expect(layoutTree(wide).viewBox.width).toBeGreaterThan(
      layoutTree(narrow).viewBox.width,
    );
    expect(layoutTree(deep).viewBox.height).toBeGreaterThan(
      layoutTree(shallow).viewBox.height,
    );
  });

  it('composes each node label from headword and lang code, sized to fit', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
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
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
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
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          depth: 0,
        },
      ],
      edges: [],
    };
    const expectedLabel = `${longHeadword} (en)`;

    const layout = layoutTree(slice);

    expect(layout.viewBox.width).toBe(widthForLabel(expectedLabel) + 2 * 16);
  });
});
