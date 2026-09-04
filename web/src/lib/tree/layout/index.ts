import type { TreeSlice } from '../../shared/types';
import {
  NODE_HEIGHT,
  NODE_STROKE_WIDTH,
  NODE_WIDTH,
  widthForLabel,
} from './nodeMetrics';
import {
  mergeDuplicateEdges,
  pickParentEdges,
  primaryRelType,
} from './parentEdges';
import type { MergedEdge } from './parentEdges';
import { trimToBoxBoundary } from './edgeClipping';
import { assignTreePorts } from './edgePorts';
import { treeEdgeMidpoint, treeEdgePath } from './edgeCurve';
import { MAX_SIBLINGS_PER_PARENT, selectCore } from './coreSelection';
import { layoutHalf } from './halfLayout';
import type {
  LayoutEdge,
  OverflowNode,
  PositionedNode,
  TreeLayout,
} from './types';

export { NODE_HEIGHT, NODE_STROKE_WIDTH, NODE_WIDTH, widthForLabel };
export { MAX_SIBLINGS_PER_PARENT };
export { primaryRelType };
export { trimToBoxBoundary };
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
  // The diagram draws only the edges that actually placed a node as a
  // parent edge in one of the two halves. Anything else (a
  // same-depth pair within a half, or an edge straddling depth 0 that
  // belongs to neither half's filtered input) has no row-to-row
  // slot to draw in and is dropped.
  const treeEdgeKeys = new Set([
    ...ancestorPick.treeEdgeKeys,
    ...descendantPick.treeEdgeKeys,
  ]);

  const edges: LayoutEdge[] = mergedEdges
    .filter(
      (edge) =>
        coreIds.has(edge.srcId) &&
        coreIds.has(edge.dstId) &&
        treeEdgeKeys.has(edgeKey(edge)),
    )
    .map((edge) => ({
      srcId: edge.srcId,
      dstId: edge.dstId,
      relTypes: edge.relTypes,
      sourceRefs: edge.sourceRefs,
    }));

  const nodeGeomById = new Map(
    positioned.map((n) => [n.id, { x: n.x, y: n.y, width: n.width }]),
  );

  const treePorts = assignTreePorts(edges, nodeGeomById);
  for (const edge of edges) {
    const srcPort = treePorts.get(`${edge.srcId}:${edge.dstId}`)!;
    const dst = nodeGeomById.get(edge.dstId)!;
    const dstBorder = trimToBoxBoundary(srcPort, dst, dst.width, NODE_HEIGHT);
    edge.path = treeEdgePath(srcPort, dstBorder);
    edge.labelPosition = treeEdgeMidpoint(srcPort, dstBorder);
  }

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
