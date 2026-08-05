import { describe, expect, it } from 'vitest';
import { layoutTree, MAX_SIBLINGS_PER_PARENT } from './treeLayout';
import type { TreeNode, TreeSlice } from '../types';

// One node with more children than the cap, at the given depth sign
// (-1 ancestors, 1 descendants), plus a grandchild hanging off the
// last (and therefore overflowed) child, to prove excluded subtrees
// are dropped entirely rather than just their direct node.
function wideFanoutSlice(depthSign: 1 | -1): TreeSlice {
  const focus: TreeNode = {
    id: 'f',
    langCode: 'en',
    headword: 'focus',
    isReconstructed: false,
    depth: 0,
  };
  const childCount = MAX_SIBLINGS_PER_PARENT + 5;
  const children: TreeNode[] = Array.from({ length: childCount }, (_, i) => ({
    id: `c${i}`,
    // Zero-padded so alphabetical order matches numeric order.
    headword: `c${String(i).padStart(2, '0')}`,
    langCode: 'en',
    isReconstructed: false,
    depth: depthSign,
  }));
  const grandchild: TreeNode = {
    id: 'gc',
    langCode: 'en',
    headword: 'grandchild',
    isReconstructed: false,
    depth: depthSign * 2,
  };
  const edge = (srcId: string, dstId: string) => ({
    srcId,
    dstId,
    relType: 'derived' as const,
    sourceRef: `${srcId}-${dstId}`,
  });
  const childEdges = children.map((c) =>
    depthSign > 0 ? edge('f', c.id) : edge(c.id, 'f'),
  );
  const lastChildId = children[children.length - 1].id;
  const grandchildEdge =
    depthSign > 0 ? edge(lastChildId, 'gc') : edge('gc', lastChildId);

  return {
    focusId: 'f',
    nodes: [focus, ...children, grandchild],
    edges: [...childEdges, grandchildEdge],
  };
}

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

  it('breaks a same-depth parent tie by rel_type priority, preferring lineage over morphology', () => {
    const slice: TreeSlice = {
      focusId: 'focus',
      nodes: [
        {
          id: 'focus',
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'A',
          langCode: 'en',
          headword: 'a-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'B',
          langCode: 'en',
          headword: 'b-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'C',
          langCode: 'en',
          headword: 'c-word',
          isReconstructed: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 'A', dstId: 'focus', relType: 'derived', sourceRef: 'rA' },
        { srcId: 'B', dstId: 'focus', relType: 'derived', sourceRef: 'rB' },
        { srcId: 'C', dstId: 'A', relType: 'affix', sourceRef: 'rCA' },
        { srcId: 'C', dstId: 'B', relType: 'inherited', sourceRef: 'rCB' },
      ],
    };

    const layout = layoutTree(slice);
    const edgeCA = layout.edges.find((e) => e.srcId === 'C' && e.dstId === 'A');
    const edgeCB = layout.edges.find((e) => e.srcId === 'C' && e.dstId === 'B');

    expect(edgeCB?.kind).toBe('tree');
    expect(edgeCA?.kind).toBe('cross-link');
  });

  it('collapses duplicate edges between the same node pair into one line', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a1',
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'a1', dstId: 'f', relType: 'root', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);

    expect(layout.edges).toHaveLength(1);
    expect(layout.edges[0].kind).toBe('tree');
    expect(layout.edges[0].relTypes.sort()).toEqual(['inherited', 'root']);
    expect(layout.edges[0].sourceRefs.sort()).toEqual(['r1', 'r2']);
  });

  it('classifies the real grandfather/father/peh₂- diamond correctly', () => {
    // ETYM-114's concrete example: grandfather has a direct affix
    // edge to father and a direct root edge to peh₂-; father also has
    // a direct root edge to that same peh₂-. treeSlice already
    // resolved peh₂- to its shortest depth (-1, direct), so both
    // father and peh₂- land at depth -1 here -- the peh₂--father edge
    // connects two same-depth nodes and can be neither's placing edge.
    const slice: TreeSlice = {
      focusId: 'gf',
      nodes: [
        {
          id: 'gf',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'father',
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'peh2',
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'father', dstId: 'gf', relType: 'affix', sourceRef: 'r1' },
        { srcId: 'peh2', dstId: 'gf', relType: 'root', sourceRef: 'r2' },
        {
          srcId: 'peh2',
          dstId: 'father',
          relType: 'root',
          sourceRef: 'r3',
        },
      ],
    };

    const layout = layoutTree(slice);

    expect(layout.edges).toHaveLength(3);
    const byPair = new Map(
      layout.edges.map((e) => [`${e.srcId}:${e.dstId}`, e]),
    );
    expect(byPair.get('father:gf')?.kind).toBe('tree');
    expect(byPair.get('peh2:gf')?.kind).toBe('tree');
    expect(byPair.get('peh2:father')?.kind).toBe('cross-link');
  });

  it('orders same-generation siblings alphabetically by headword', () => {
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
          id: 'z',
          langCode: 'en',
          headword: 'zeta',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'a',
          langCode: 'en',
          headword: 'alpha',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'm',
          langCode: 'en',
          headword: 'mid',
          isReconstructed: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'z', dstId: 'f', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'a', dstId: 'f', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'm', dstId: 'f', relType: 'derived', sourceRef: 'r3' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get('a')!.x).toBeLessThan(byId.get('m')!.x);
    expect(byId.get('m')!.x).toBeLessThan(byId.get('z')!.x);
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

  it('falls back to the focus as parent when a node has no edge reaching its resolved depth', () => {
    // x sits at depth -1 but its only edges are a cyclic pair with
    // a, another depth -1 node -- neither edge reaches depth 0, so
    // pickParentEdges finds no valid candidate for x and must fall
    // back to the focus rather than crashing.
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
          id: 'x',
          langCode: 'en',
          headword: 'x-word',
          isReconstructed: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'a', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'x', dstId: 'a', relType: 'cognate', sourceRef: 'r2' },
        { srcId: 'a', dstId: 'x', relType: 'cognate', sourceRef: 'r3' },
      ],
    };

    expect(() => layoutTree(slice)).not.toThrow();

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get('x')).toBeDefined();
    // Falling back to the focus makes x a direct child of f, at the
    // same tree row as a (also a direct child of f).
    expect(byId.get('x')!.y).toBe(byId.get('a')!.y);
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

  it('caps a descendant fan-out to the first N children alphabetically', () => {
    const slice = wideFanoutSlice(1);
    const layout = layoutTree(slice);
    const renderedIds = new Set(layout.nodes.map((n) => n.id));

    for (let i = 0; i < MAX_SIBLINGS_PER_PARENT; i++) {
      expect(renderedIds.has(`c${i}`)).toBe(true);
    }
    expect(renderedIds.has(`c${MAX_SIBLINGS_PER_PARENT}`)).toBe(false);
    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 'f', count: 5 }),
    ]);
  });

  it('caps an ancestor fan-out the same way as a descendant one', () => {
    const slice = wideFanoutSlice(-1);
    const layout = layoutTree(slice);
    const renderedIds = new Set(layout.nodes.map((n) => n.id));

    expect(renderedIds.has('c0')).toBe(true);
    expect(renderedIds.has(`c${MAX_SIBLINGS_PER_PARENT}`)).toBe(false);
    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 'f', count: 5 }),
    ]);
  });

  it("excludes an overflowed child's entire subtree, not just the child", () => {
    const slice = wideFanoutSlice(1);
    const layout = layoutTree(slice);

    expect(layout.nodes.some((n) => n.id === 'gc')).toBe(false);
  });

  it('keeps the focus in the core no matter how wide its fan-out is', () => {
    const slice = wideFanoutSlice(1);
    const layout = layoutTree(slice);

    expect(layout.nodes.some((n) => n.id === 'f' && n.isFocus)).toBe(true);
  });

  it('keeps the most etymologically relevant siblings, not the alphabetically first ones', () => {
    // 10 cognate children (c00..c09, alphabetically first) plus 2
    // inherited children (z0, z1, alphabetically last) exceed the cap
    // by 2. Direct lineage (inherited) must survive the cap over mere
    // cognates regardless of alphabetical order, so the 2 dropped
    // should be the lowest-priority tier's own alphabetical tail
    // (c08, c09), not z0/z1.
    const focus: TreeNode = {
      id: 'f',
      langCode: 'en',
      headword: 'focus',
      isReconstructed: false,
      depth: 0,
    };
    const cognates: TreeNode[] = Array.from({ length: 10 }, (_, i) => ({
      id: `c${String(i).padStart(2, '0')}`,
      headword: `c${String(i).padStart(2, '0')}`,
      langCode: 'en',
      isReconstructed: false,
      depth: 1,
    }));
    const lineage: TreeNode[] = ['z0', 'z1'].map((id) => ({
      id,
      headword: id,
      langCode: 'en',
      isReconstructed: false,
      depth: 1,
    }));
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [focus, ...cognates, ...lineage],
      edges: [
        ...cognates.map((c) => ({
          srcId: 'f',
          dstId: c.id,
          relType: 'cognate' as const,
          sourceRef: `r-${c.id}`,
        })),
        ...lineage.map((l) => ({
          srcId: 'f',
          dstId: l.id,
          relType: 'inherited' as const,
          sourceRef: `r-${l.id}`,
        })),
      ],
    };

    const layout = layoutTree(slice);
    const renderedIds = new Set(layout.nodes.map((n) => n.id));

    expect(renderedIds.has('z0')).toBe(true);
    expect(renderedIds.has('z1')).toBe(true);
    for (let i = 0; i < 8; i++) {
      expect(renderedIds.has(`c${String(i).padStart(2, '0')}`)).toBe(true);
    }
    expect(renderedIds.has('c08')).toBe(false);
    expect(renderedIds.has('c09')).toBe(false);
    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 'f', count: 2 }),
    ]);
  });

  it('reveals every child of an expanded parent, clearing its overflow entry', () => {
    const slice = wideFanoutSlice(1);
    const layout = layoutTree(slice, new Set(['f']));
    const renderedIds = new Set(layout.nodes.map((n) => n.id));

    for (let i = 0; i < MAX_SIBLINGS_PER_PARENT + 5; i++) {
      expect(renderedIds.has(`c${i}`)).toBe(true);
    }
    expect(renderedIds.has('gc')).toBe(true);
    expect(layout.overflow).toEqual([]);
  });

  it('does not create an overflow entry when a fan-out is within the cap', () => {
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
          id: 'a1',
          langCode: 'en',
          headword: 'a1',
          isReconstructed: false,
          depth: 1,
        },
      ],
      edges: [{ srcId: 'f', dstId: 'a1', relType: 'derived', sourceRef: 'r' }],
    };

    expect(layoutTree(slice).overflow).toEqual([]);
  });

  it("adds the server's reported overflow even when every fetched child fits under the cap", () => {
    // ETYM-144: the server now caps fan-out during the fetch itself,
    // so a parent with a real 15k-wide fan-out arrives with only the
    // top 10 present -- nothing for selectCore to locally exclude --
    // plus an explicit count of what was never fetched at all.
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
          id: 'a1',
          langCode: 'en',
          headword: 'a1',
          isReconstructed: false,
          depth: 1,
        },
      ],
      edges: [{ srcId: 'f', dstId: 'a1', relType: 'derived', sourceRef: 'r' }],
      overflow: [{ parentId: 'f', direction: 'descendant', count: 15184 }],
    };

    const layout = layoutTree(slice);

    expect(layout.overflow).toEqual([
      expect.objectContaining({
        parentId: 'f',
        direction: 'descendant',
        count: 15184,
      }),
    ]);
  });

  it('keeps showing server-reported overflow after a parent is locally expanded', () => {
    // A parent already in expandedParents shows every child currently
    // present with no local overflow of its own -- but if the server
    // still has more that was never fetched, that count must survive
    // regardless, since "everything present is shown" and "more
    // exists unfetched" are independent facts.
    const slice = wideFanoutSlice(1);
    const withServerOverflow: TreeSlice = {
      ...slice,
      overflow: [{ parentId: 'f', direction: 'descendant', count: 3 }],
    };

    const layout = layoutTree(withServerOverflow, new Set(['f']));

    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 'f', count: 3 }),
    ]);
  });

  it('tags each overflow entry with its direction', () => {
    const slice = wideFanoutSlice(-1);
    const layout = layoutTree(slice);

    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 'f', direction: 'ancestor' }),
    ]);
  });
});
