import { describe, expect, it } from 'vitest';
import { layoutTree, MAX_SIBLINGS_PER_PARENT } from './index';
import type { TreeNode, TreeSlice } from '../../shared/types';

// One node with more children than the cap, at the given depth sign
// (-1 ancestors, 1 descendants), plus a grandchild hanging off the
// last (and therefore overflowed) child, to prove excluded subtrees
// are dropped entirely rather than just their direct node.
function wideFanoutSlice(depthSign: 1 | -1): TreeSlice {
  const focus: TreeNode = {
    id: 1,
    langCode: 'en',
    headword: 'focus',
    isReconstructed: false,
    isRedlink: false,
    depth: 0,
  };
  const childCount = MAX_SIBLINGS_PER_PARENT + 5;
  const children: TreeNode[] = Array.from({ length: childCount }, (_, i) => ({
    id: 100 + i,
    // Zero-padded so alphabetical order matches numeric order.
    headword: `c${String(i).padStart(2, '0')}`,
    langCode: 'en',
    isReconstructed: false,
    isRedlink: false,
    depth: depthSign,
  }));
  const grandchild: TreeNode = {
    id: 2,
    langCode: 'en',
    headword: 'grandchild',
    isReconstructed: false,
    isRedlink: false,
    depth: depthSign * 2,
  };
  const edge = (srcId: number, dstId: number) => ({
    srcId,
    dstId,
    relType: 'derived' as const,
    sourceRef: `${srcId}-${dstId}`,
  });
  const childEdges = children.map((c) =>
    depthSign > 0 ? edge(1, c.id) : edge(c.id, 1),
  );
  const lastChildId = children[children.length - 1].id;
  const grandchildEdge =
    depthSign > 0 ? edge(lastChildId, 2) : edge(2, lastChildId);

  return {
    focusId: 1,
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
      expect(renderedIds.has(100 + i)).toBe(true);
    }
    expect(renderedIds.has(100 + MAX_SIBLINGS_PER_PARENT)).toBe(false);
    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 1, count: 5 }),
    ]);
  });

  it('caps an ancestor fan-out the same way as a descendant one', () => {
    const slice = wideFanoutSlice(-1);
    const layout = layoutTree(slice);
    const renderedIds = new Set(layout.nodes.map((n) => n.id));

    expect(renderedIds.has(100)).toBe(true);
    expect(renderedIds.has(100 + MAX_SIBLINGS_PER_PARENT)).toBe(false);
    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 1, count: 5 }),
    ]);
  });

  it("excludes an overflowed child's entire subtree, not just the child", () => {
    const slice = wideFanoutSlice(1);
    const layout = layoutTree(slice);

    expect(layout.nodes.some((n) => n.id === 2)).toBe(false);
  });

  it('keeps the focus in the core no matter how wide its fan-out is', () => {
    const slice = wideFanoutSlice(1);
    const layout = layoutTree(slice);

    expect(layout.nodes.some((n) => n.id === 1 && n.isFocus)).toBe(true);
  });

  it('keeps the most etymologically relevant siblings, not the alphabetically first ones', () => {
    // 10 mention children (c00..c09, alphabetically first) plus 2
    // inherited children (z0, z1, alphabetically last) exceed the cap
    // by 2. Direct lineage (inherited) must survive the cap over mere
    // mentions regardless of alphabetical order, so the 2 dropped
    // should be the lowest-priority tier's own alphabetical tail
    // (c08, c09), not z0/z1.
    const focus: TreeNode = {
      id: 1,
      langCode: 'en',
      headword: 'focus',
      isReconstructed: false,
      isRedlink: false,
      depth: 0,
    };
    const mentions: TreeNode[] = Array.from({ length: 10 }, (_, i) => ({
      id: 100 + i,
      headword: `c${String(i).padStart(2, '0')}`,
      langCode: 'en',
      isReconstructed: false,
      isRedlink: false,
      depth: 1,
    }));
    const lineage: TreeNode[] = [200, 201].map((id) => ({
      id,
      headword: `z${id - 200}`,
      langCode: 'en',
      isReconstructed: false,
      isRedlink: false,
      depth: 1,
    }));
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [focus, ...mentions, ...lineage],
      edges: [
        ...mentions.map((c) => ({
          srcId: 1,
          dstId: c.id,
          relType: 'mention' as const,
          sourceRef: `r-${c.id}`,
        })),
        ...lineage.map((l) => ({
          srcId: 1,
          dstId: l.id,
          relType: 'inherited' as const,
          sourceRef: `r-${l.id}`,
        })),
      ],
    };

    const layout = layoutTree(slice);
    const renderedIds = new Set(layout.nodes.map((n) => n.id));

    expect(renderedIds.has(200)).toBe(true);
    expect(renderedIds.has(201)).toBe(true);
    for (let i = 0; i < 8; i++) {
      expect(renderedIds.has(100 + i)).toBe(true);
    }
    expect(renderedIds.has(108)).toBe(false);
    expect(renderedIds.has(109)).toBe(false);
    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 1, count: 2 }),
    ]);
  });

  it('reveals every child of an expanded parent, clearing its overflow entry', () => {
    const slice = wideFanoutSlice(1);
    const layout = layoutTree(slice, new Set([1]));
    const renderedIds = new Set(layout.nodes.map((n) => n.id));

    for (let i = 0; i < MAX_SIBLINGS_PER_PARENT + 5; i++) {
      expect(renderedIds.has(100 + i)).toBe(true);
    }
    expect(renderedIds.has(2)).toBe(true);
    expect(layout.overflow).toEqual([]);
  });

  it('does not create an overflow entry when a fan-out is within the cap', () => {
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
          id: 3,
          langCode: 'en',
          headword: 'a1',
          isReconstructed: false,
          isRedlink: false,
          depth: 1,
        },
      ],
      edges: [{ srcId: 1, dstId: 3, relType: 'derived', sourceRef: 'r' }],
    };

    expect(layoutTree(slice).overflow).toEqual([]);
  });

  it("adds the server's reported overflow even when every fetched child fits under the cap", () => {
    // The server now caps fan-out during the fetch itself, so a
    // parent with a real 15k-wide fan-out arrives with only the top
    // 10 present (nothing for selectCore to locally exclude) plus
    // an explicit count of what was never fetched at all.
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
          id: 3,
          langCode: 'en',
          headword: 'a1',
          isReconstructed: false,
          isRedlink: false,
          depth: 1,
        },
      ],
      edges: [{ srcId: 1, dstId: 3, relType: 'derived', sourceRef: 'r' }],
      overflow: [{ parentId: 1, direction: 'descendant', count: 15184 }],
    };

    const layout = layoutTree(slice);

    expect(layout.overflow).toEqual([
      expect.objectContaining({
        parentId: 1,
        direction: 'descendant',
        count: 15184,
      }),
    ]);
  });

  it('keeps showing server-reported overflow after a parent is locally expanded', () => {
    // A parent already in expandedParents shows every child currently
    // present with no local overflow of its own, but if the server
    // still has more that was never fetched, that count must survive
    // regardless, since "everything present is shown" and "more
    // exists unfetched" are independent facts.
    const slice = wideFanoutSlice(1);
    const withServerOverflow: TreeSlice = {
      ...slice,
      overflow: [{ parentId: 1, direction: 'descendant', count: 3 }],
    };

    const layout = layoutTree(withServerOverflow, new Set([1]));

    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 1, count: 3 }),
    ]);
  });

  it('tags each overflow entry with its direction', () => {
    const slice = wideFanoutSlice(-1);
    const layout = layoutTree(slice);

    expect(layout.overflow).toEqual([
      expect.objectContaining({ parentId: 1, direction: 'ancestor' }),
    ]);
  });
});
