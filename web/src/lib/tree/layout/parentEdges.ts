import type { EtymRelType, TreeEdge } from '../../shared/types';

// Direct lineage relations outrank morphological decomposition when a
// converging node has more than one edge landing it at its own
// resolved depth, so the diagram's spine follows descent rather than
// word-part breakdown.
const REL_TYPE_PRIORITY: Record<EtymRelType, number> = {
  inherited: 0,
  borrowed: 1,
  learned_borrowing: 2,
  semi_learned_borrowing: 3,
  transliteration: 4,
  derived: 5,
  shortening: 6,
  metathesis: 7,
  inflection: 8,
  calque: 9,
  semantic_loan: 10,
  compound: 11,
  blend: 12,
  univerbation: 13,
  affix: 14,
  reduplication: 15,
  surface_analysis: 16,
  root: 17,
  influence: 18,
  mention: 19,
};

// The relType shown as an edge's label when mergeDuplicateEdges has
// collapsed more than one rel_type onto the same src/dst pair: the
// same lineage-over-morphology ranking pickParentEdges already uses to
// break same-depth parent ties.
export function primaryRelType(relTypes: EtymRelType[]): EtymRelType {
  let best = relTypes[0];
  for (const relType of relTypes) {
    if (REL_TYPE_PRIORITY[relType] < REL_TYPE_PRIORITY[best]) best = relType;
  }
  return best;
}

export interface MergedEdge {
  srcId: number;
  dstId: number;
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

function otherEnd(edge: MergedEdge, nodeId: number): number {
  return edge.srcId === nodeId ? edge.dstId : edge.srcId;
}

function towardFocusDepth(depth: number): number {
  return depth < 0 ? depth + 1 : depth - 1;
}

// Priority ceiling for "descent" relTypes (inherited through
// metathesis); see REL_TYPE_PRIORITY. Below this, an edge asserts real
// lineage; at or above it, an edge is morphological decomposition or weaker
// (compound/affix/root/...), where a same-depth tie is a
// genuine structural diamond, not a restated ancestor.
const LINEAGE_PRIORITY_CEILING = 8;

// True when `edge` runs from `nodeId` toward `other` on the side of
// the tree that moves toward the focus, i.e. `nodeId` is `edge`'s
// etymological ancestor side and `other` is one hop closer to the
// focus. Direction is taken from the edge itself, not from depth,
// since depth alone can't distinguish a real placing edge from one
// that runs the opposite way but happens to land at the same depth
// (a depth inversion) or tie.
function isTowardFocus(
  edge: MergedEdge,
  nodeId: number,
  other: number,
  isAncestorHalf: boolean,
): boolean {
  return isAncestorHalf
    ? edge.srcId === nodeId && edge.dstId === other
    : edge.dstId === nodeId && edge.srcId === other;
}

// True when `edge` is a lineage edge running from `nodeId` toward
// `other`, i.e. `nodeId` is `edge`'s etymological ancestor side and
// `other` is one lineage hop closer to the focus. Direction is taken
// from the edge itself, not from depth, since a tie means both ends
// share the same BFS depth.
function isLineageChainCandidate(
  edge: MergedEdge,
  nodeId: number,
  other: number,
  isAncestorHalf: boolean,
): boolean {
  if (bestRank(edge) > LINEAGE_PRIORITY_CEILING) return false;
  return isTowardFocus(edge, nodeId, other, isAncestorHalf);
}

// For every non-focus node, picks the single edge that places it at
// its own resolved depth (tie-broken by rel_type priority, then the
// neighboring node's id). Those placing edges are the tree; every
// other edge in this half (including one whose two endpoints sit at
// the same depth, which can never be either endpoint's placing edge)
// is left out of the diagram.
export function pickParentEdges(
  nodeIds: number[],
  focusId: number,
  depthOf: Map<number, number>,
  edges: MergedEdge[],
): {
  parentIdOf: Map<number, number>;
  parentEdgeRankOf: Map<number, number>;
  parentEdgePieceOrderOf: Map<number, number | null>;
  treeEdgeKeys: Set<string>;
} {
  const incident = new Map<number, MergedEdge[]>();
  for (const edge of edges) {
    for (const id of [edge.srcId, edge.dstId]) {
      const list = incident.get(id) ?? [];
      list.push(edge);
      incident.set(id, list);
    }
  }

  const parentIdOf = new Map<number, number>();
  const parentEdgeRankOf = new Map<number, number>();
  const parentEdgePieceOrderOf = new Map<number, number | null>();
  const treeEdgeKeys = new Set<string>();

  const rankThenAlpha =
    (nodeId: number) =>
    (a: MergedEdge, b: MergedEdge): number => {
      const rankDiff = bestRank(a) - bestRank(b);
      if (rankDiff !== 0) return rankDiff;
      return otherEnd(a, nodeId) - otherEnd(b, nodeId);
    };

  for (const nodeId of nodeIds) {
    if (nodeId === focusId) continue;
    const nodeDepth = depthOf.get(nodeId)!;
    const target = towardFocusDepth(nodeDepth);
    const isAncestorHalf = nodeDepth <= 0;
    const direct: MergedEdge[] = [];
    // A direct-to-focus edge can tie in BFS depth with another direct
    // ancestor that is itself one lineage hop closer to this node --
    // Wiktionary independently citing both the immediate and a deeper
    // ancestor for the same descent. Chaining through that
    // nearer ancestor re-homes this node to its true chain position
    // instead of rendering it as a duplicate tied sibling.
    const chained: MergedEdge[] = [];
    for (const edge of incident.get(nodeId) ?? []) {
      const other = otherEnd(edge, nodeId);
      if (
        depthOf.get(other) === target &&
        isTowardFocus(edge, nodeId, other, isAncestorHalf)
      ) {
        direct.push(edge);
      } else if (
        depthOf.get(other) === nodeDepth &&
        isLineageChainCandidate(edge, nodeId, other, isAncestorHalf)
      ) {
        chained.push(edge);
      }
    }
    chained.sort(rankThenAlpha(nodeId));
    direct.sort(rankThenAlpha(nodeId));
    const candidates = [...chained, ...direct];
    const chosen = candidates[0];
    if (!chosen) {
      // treeSlice()'s shortest-path depth can place a node one hop
      // closer to the focus than any single edge in this half
      // actually reaches (e.g. a cyclic pair of edges). Fall back to
      // the focus itself so stratify() still gets a valid parent.
      // No real edge backs this placement, so it ranks last: it has
      // no lineage relevance to claim over a sibling that does.
      parentIdOf.set(nodeId, focusId);
      continue;
    }
    parentIdOf.set(nodeId, otherEnd(chosen, nodeId));
    parentEdgeRankOf.set(nodeId, bestRank(chosen));
    parentEdgePieceOrderOf.set(nodeId, bestPieceOrder(chosen));
    treeEdgeKeys.add(`${chosen.srcId}:${chosen.dstId}`);
  }

  return { parentIdOf, parentEdgeRankOf, parentEdgePieceOrderOf, treeEdgeKeys };
}
