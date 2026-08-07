import { describe, expect, it } from 'vitest';
import { layoutTree, MAX_SIBLINGS_PER_PARENT } from './index';
import type { TreeNode, TreeSlice } from '../../types';

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

describe('fan-out capping', () => {
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
    // The server now caps fan-out during the fetch itself, so a
    // parent with a real 15k-wide fan-out arrives with only the top
    // 10 present -- nothing for selectCore to locally exclude -- plus
    // an explicit count of what was never fetched at all.
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
