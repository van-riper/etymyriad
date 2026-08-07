import type { TreeSlice } from '../../shared/types';
import {
  NODE_HEIGHT,
  NODE_STROKE_WIDTH,
  NODE_WIDTH,
  widthForLabel,
} from './nodeMetrics';
import { mergeDuplicateEdges, pickParentEdges } from './parentEdges';
import type { MergedEdge } from './parentEdges';
import { MAX_SIBLINGS_PER_PARENT, selectCore } from './coreSelection';
import { layoutHalf } from './halfLayout';
import { routeCrossLinks } from './crossLinkRouting';
import type {
  LayoutEdge,
  OverflowNode,
  PositionedNode,
  TreeLayout,
} from './types';

export { NODE_HEIGHT, NODE_STROKE_WIDTH, NODE_WIDTH, widthForLabel };
export { MAX_SIBLINGS_PER_PARENT };
export type {
  LayoutEdge,
  OverflowNode,
  PositionedNode,
  TreeLayout,
  ViewBox,
} from './types';

const PADDING = 16;

export function layoutTree(
  slice: TreeSlice,
  expandedParents: ReadonlySet<string> = new Set(),
): TreeLayout {
  const depthOf = new Map(slice.nodes.map((n) => [n.id, n.depth]));
  const mergedEdges = mergeDuplicateEdges(slice.edges);

  const ancestorNodes = slice.nodes.filter((n) => n.depth <= 0);
  const descendantNodes = slice.nodes.filter((n) => n.depth >= 0);

  const ancestorEdges = mergedEdges.filter(
    (e) => depthOf.get(e.srcId)! <= 0 && depthOf.get(e.dstId)! <= 0,
  );
  const descendantEdges = mergedEdges.filter(
    (e) => depthOf.get(e.srcId)! >= 0 && depthOf.get(e.dstId)! >= 0,
  );

  const ancestorPick = pickParentEdges(
    ancestorNodes.map((n) => n.id),
    slice.focusId,
    depthOf,
    ancestorEdges,
  );
  const descendantPick = pickParentEdges(
    descendantNodes.map((n) => n.id),
    slice.focusId,
    depthOf,
    descendantEdges,
  );

  const serverOverflowFor = (
    direction: 'ancestor' | 'descendant',
  ): Map<string, number> =>
    new Map(
      (slice.overflow ?? [])
        .filter((o) => o.direction === direction)
        .map((o) => [o.parentId, o.count]),
    );

  const ancestorCore = selectCore(
    ancestorNodes,
    slice.focusId,
    ancestorPick.parentIdOf,
    ancestorPick.parentEdgeRankOf,
    expandedParents,
    serverOverflowFor('ancestor'),
  );
  const descendantCore = selectCore(
    descendantNodes,
    slice.focusId,
    descendantPick.parentIdOf,
    descendantPick.parentEdgeRankOf,
    expandedParents,
    serverOverflowFor('descendant'),
  );

  const ancestorHalf = layoutHalf(
    ancestorNodes,
    slice.focusId,
    ancestorPick.parentIdOf,
    ancestorPick.parentEdgePieceOrderOf,
    ancestorCore,
  );
  const descendantHalf = layoutHalf(
    descendantNodes,
    slice.focusId,
    descendantPick.parentIdOf,
    descendantPick.parentEdgePieceOrderOf,
    descendantCore,
  );

  const coreIds = new Set([...ancestorCore.coreIds, ...descendantCore.coreIds]);

  // sign * 0 yields -0 for a depth-0 node/marker in the negated
  // (ancestor) half; Object.is(-0, 0) is false, which fails Vitest's
  // toBe/toMatchObject against a plain 0, so normalize back to
  // positive zero.
  const signY = (y: number, sign: 1 | -1) => (y === 0 ? 0 : sign * y);

  const positioned: PositionedNode[] = slice.nodes
    .filter((node) => coreIds.has(node.id))
    .map((node) => {
      const raw =
        node.depth <= 0
          ? ancestorHalf.positions.get(node.id)!
          : descendantHalf.positions.get(node.id)!;
      return {
        ...node,
        x: raw.x,
        y: signY(raw.y, node.depth <= 0 ? -1 : 1),
        isFocus: node.id === slice.focusId,
        label: raw.label,
        width: raw.width,
      };
    });

  const overflow: OverflowNode[] = [
    ...ancestorHalf.overflow.map((o) => ({
      ...o,
      direction: 'ancestor' as const,
      y: signY(o.y, -1),
    })),
    ...descendantHalf.overflow.map((o) => ({
      ...o,
      direction: 'descendant' as const,
      y: signY(o.y, 1),
    })),
  ];

  const edgeKey = (e: MergedEdge) => `${e.srcId}:${e.dstId}`;
  const ancestorKeys = new Set(ancestorEdges.map(edgeKey));
  const descendantKeys = new Set(descendantEdges.map(edgeKey));
  const ancestorCrossLinkKeys = new Set(ancestorPick.crossLinks.map(edgeKey));
  const descendantCrossLinkKeys = new Set(
    descendantPick.crossLinks.map(edgeKey),
  );

  const edges: LayoutEdge[] = mergedEdges
    .filter((edge) => coreIds.has(edge.srcId) && coreIds.has(edge.dstId))
    .map((edge) => {
      const key = edgeKey(edge);
      // An edge is 'tree' only if it was actually placed as a node's
      // parent edge in one of the two halves. Anything else -- a
      // same-depth pair within a half, or an edge straddling depth 0
      // that belongs to neither half's filtered input -- is a
      // cross-link by construction, not by a default fallback.
      const isTree =
        (ancestorKeys.has(key) && !ancestorCrossLinkKeys.has(key)) ||
        (descendantKeys.has(key) && !descendantCrossLinkKeys.has(key));
      return {
        srcId: edge.srcId,
        dstId: edge.dstId,
        relTypes: edge.relTypes,
        sourceRefs: edge.sourceRefs,
        kind: isTree ? 'tree' : 'cross-link',
      };
    });

  routeCrossLinks(
    edges,
    new Map(positioned.map((n) => [n.id, { x: n.x, y: n.y }])),
  );

  const ys = [...positioned.map((n) => n.y), ...overflow.map((o) => o.y)];
  const xMins = [
    ...positioned.map((n) => n.x - n.width / 2),
    ...overflow.map((o) => o.x - o.width / 2),
  ];
  const xMaxs = [
    ...positioned.map((n) => n.x + n.width / 2),
    ...overflow.map((o) => o.x + o.width / 2),
  ];
  const minX = Math.min(...xMins) - PADDING;
  const maxX = Math.max(...xMaxs) + PADDING;
  const minY = Math.min(...ys) - NODE_HEIGHT / 2 - PADDING;
  const maxY = Math.max(...ys) + NODE_HEIGHT / 2 + PADDING;

  return {
    nodes: positioned,
    edges,
    overflow,
    viewBox: { minX, minY, width: maxX - minX, height: maxY - minY },
  };
}
