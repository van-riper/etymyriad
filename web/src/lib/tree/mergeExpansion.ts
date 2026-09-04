import type {
  TreeEdge,
  TreeNode,
  TreeOverflow,
  TreeSlice,
} from '../shared/types';

export interface TreeExpansion {
  nodes: TreeNode[];
  edges: TreeEdge[];
  overflow: TreeOverflow[];
}

// Folds a "+N more" expansion fetch into the slice
// already rendered: appends whatever's new, and replaces the
// expanded parent's own overflow entry with what the server reports
// remaining, dropped entirely once nothing remains. Any other
// overflow entry the expansion reports (a newly revealed child that's
// itself over the cap) is added, not merged, since it's new. Every
// other parent's existing overflow entry is left untouched.
export function mergeTreeExpansion(
  slice: TreeSlice,
  parentId: string,
  direction: 'ancestor' | 'descendant',
  expansion: TreeExpansion,
): TreeSlice {
  const knownNodeIds = new Set(slice.nodes.map((n) => n.id));
  const newNodes = expansion.nodes.filter((n) => !knownNodeIds.has(n.id));

  const edgeKey = (e: TreeEdge) => `${e.srcId}:${e.dstId}:${e.relType}`;
  const knownEdgeKeys = new Set(slice.edges.map(edgeKey));
  const newEdges = expansion.edges.filter(
    (e) => !knownEdgeKeys.has(edgeKey(e)),
  );

  const overflowKey = (o: TreeOverflow) => `${o.parentId}:${o.direction}`;
  const overflowByKey = new Map<string, TreeOverflow>(
    (slice.overflow ?? []).map((o) => [overflowKey(o), o]),
  );
  overflowByKey.delete(`${parentId}:${direction}`);
  for (const o of expansion.overflow) {
    overflowByKey.set(overflowKey(o), o);
  }

  return {
    ...slice,
    nodes: [...slice.nodes, ...newNodes],
    edges: [...slice.edges, ...newEdges],
    overflow: [...overflowByKey.values()],
  };
}
