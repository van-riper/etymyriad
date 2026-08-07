import type { EtymRelType, TreeEdge } from '../../types';

// Direct lineage relations outrank morphological decomposition when a
// converging node has more than one edge landing it at its own
// resolved depth, so the diagram's spine follows descent rather than
// word-part breakdown. cognate/onomatopoeic have no rows in the
// loaded dataset and weren't in that ranking; placed last so the
// lookup stays exhaustive over EtymRelType.
const REL_TYPE_PRIORITY: Record<EtymRelType, number> = {
  inherited: 0,
  borrowed: 1,
  learned_borrowing: 2,
  semi_learned_borrowing: 3,
  derived: 4,
  calque: 5,
  compound: 6,
  affix: 7,
  root: 8,
  mention: 9,
  cognate: 10,
  onomatopoeic: 11,
};

export interface MergedEdge {
  srcId: string;
  dstId: string;
  relTypes: EtymRelType[];
  sourceRefs: string[];
  pieceOrders: Array<number | null>;
}

export function mergeDuplicateEdges(edges: TreeEdge[]): MergedEdge[] {
  const byPair = new Map<string, MergedEdge>();
  for (const edge of edges) {
    const key = `${edge.srcId}:${edge.dstId}`;
    const existing = byPair.get(key);
    if (existing) {
      existing.relTypes.push(edge.relType);
      existing.sourceRefs.push(edge.sourceRef);
      existing.pieceOrders.push(edge.pieceOrder ?? null);
    } else {
      byPair.set(key, {
        srcId: edge.srcId,
        dstId: edge.dstId,
        relTypes: [edge.relType],
        sourceRefs: [edge.sourceRef],
        pieceOrders: [edge.pieceOrder ?? null],
      });
    }
  }
  return [...byPair.values()];
}

function bestRankIndex(edge: MergedEdge): number {
  let bestIndex = 0;
  for (let i = 1; i < edge.relTypes.length; i++) {
    if (
      REL_TYPE_PRIORITY[edge.relTypes[i]] <
      REL_TYPE_PRIORITY[edge.relTypes[bestIndex]]
    ) {
      bestIndex = i;
    }
  }
  return bestIndex;
}

function bestRank(edge: MergedEdge): number {
  return REL_TYPE_PRIORITY[edge.relTypes[bestRankIndex(edge)]];
}

// The composition-piece position (1-based: prefix, root, suffix, ...)
// of the relType that actually won this edge's rank, or null when that
// relType never decomposes a word into ordered pieces.
function bestPieceOrder(edge: MergedEdge): number | null {
  return edge.pieceOrders[bestRankIndex(edge)];
}

function otherEnd(edge: MergedEdge, nodeId: string): string {
  return edge.srcId === nodeId ? edge.dstId : edge.srcId;
}

function towardFocusDepth(depth: number): number {
  return depth < 0 ? depth + 1 : depth - 1;
}

// For every non-focus node, picks the single edge that places it at
// its own resolved depth (tie-broken by rel_type priority, then the
// neighboring node's id). Every other edge in this half -- including
// one whose two endpoints sit at the same depth, which can never be
// either endpoint's placing edge -- is a cross-link.
export function pickParentEdges(
  nodeIds: string[],
  focusId: string,
  depthOf: Map<string, number>,
  edges: MergedEdge[],
): {
  parentIdOf: Map<string, string>;
  parentEdgeRankOf: Map<string, number>;
  parentEdgePieceOrderOf: Map<string, number | null>;
  crossLinks: MergedEdge[];
} {
  const incident = new Map<string, MergedEdge[]>();
  for (const edge of edges) {
    for (const id of [edge.srcId, edge.dstId]) {
      const list = incident.get(id) ?? [];
      list.push(edge);
      incident.set(id, list);
    }
  }

  const parentIdOf = new Map<string, string>();
  const parentEdgeRankOf = new Map<string, number>();
  const parentEdgePieceOrderOf = new Map<string, number | null>();
  const usedKeys = new Set<string>();

  for (const nodeId of nodeIds) {
    if (nodeId === focusId) continue;
    const target = towardFocusDepth(depthOf.get(nodeId)!);
    const candidates = (incident.get(nodeId) ?? []).filter(
      (edge) => depthOf.get(otherEnd(edge, nodeId)) === target,
    );
    candidates.sort((a, b) => {
      const rankDiff = bestRank(a) - bestRank(b);
      if (rankDiff !== 0) return rankDiff;
      return otherEnd(a, nodeId).localeCompare(otherEnd(b, nodeId), 'en');
    });
    const chosen = candidates[0];
    if (!chosen) {
      // treeSlice()'s shortest-path depth can place a node one hop
      // closer to the focus than any single edge in this half
      // actually reaches (e.g. a cyclic pair of edges). Fall back to
      // the focus itself so stratify() still gets a valid parent.
      // No real edge backs this placement, so it ranks last -- it has
      // no lineage relevance to claim over a sibling that does.
      parentIdOf.set(nodeId, focusId);
      continue;
    }
    parentIdOf.set(nodeId, otherEnd(chosen, nodeId));
    parentEdgeRankOf.set(nodeId, bestRank(chosen));
    parentEdgePieceOrderOf.set(nodeId, bestPieceOrder(chosen));
    usedKeys.add(`${chosen.srcId}:${chosen.dstId}`);
  }

  const crossLinks = edges.filter(
    (edge) => !usedKeys.has(`${edge.srcId}:${edge.dstId}`),
  );
  return { parentIdOf, parentEdgeRankOf, parentEdgePieceOrderOf, crossLinks };
}
