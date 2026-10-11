import { NODE_HEIGHT } from './nodeMetrics';
import type { LayoutEdge } from './types';

interface Point {
  x: number;
  y: number;
}

interface NodeGeom {
  x: number;
  y: number;
  width: number;
}

const PORT_SPREAD_FRACTION = 0.6;

// n=1 -> [0], preserving a single edge's centered look exactly.
// n>=2 -> evenly spread across PORT_SPREAD_FRACTION of `span`, ordered
// so callers assign them in the same top-to-bottom order as the
// edges' other endpoints, keeping ports uncrossed along the node's
// side and off its rounded corners.
export function portOffsets(count: number, span: number): number[] {
  if (count <= 1) return [0];
  const usable = span * PORT_SPREAD_FRACTION;
  const step = usable / (count - 1);
  return Array.from({ length: count }, (_, i) => -usable / 2 + i * step);
}

// A tree edge always runs src (parent, smaller x) -> dst (child,
// larger x) in both halves (the ancestor half's x is negated as a
// whole, so "ancestor -> descendant" still means "smaller x -> larger
// x" locally). A parent with several children converges every one of
// those edges on the exact same point today; this spreads them across
// the parent's right border, in the children's own y order, instead.
// The child side stays centered: a node has exactly one tree-parent
// edge, so there's nothing to spread there.
export function assignTreePorts(
  edges: LayoutEdge[],
  nodeById: Map<number, NodeGeom>,
): Map<string, Point> {
  const byParent = new Map<number, LayoutEdge[]>();
  for (const edge of edges) {
    const children = byParent.get(edge.srcId) ?? [];
    children.push(edge);
    byParent.set(edge.srcId, children);
  }

  const portByEdgeKey = new Map<string, Point>();
  for (const [parentId, children] of byParent) {
    const parent = nodeById.get(parentId);
    if (!parent) continue;
    const ordered = [...children].sort(
      (a, b) => nodeById.get(a.dstId)!.y - nodeById.get(b.dstId)!.y,
    );
    const offsets = portOffsets(ordered.length, NODE_HEIGHT);
    ordered.forEach((edge, i) => {
      portByEdgeKey.set(`${edge.srcId}:${edge.dstId}`, {
        x: parent.x + parent.width / 2,
        y: parent.y + offsets[i],
      });
    });
  }
  return portByEdgeKey;
}
