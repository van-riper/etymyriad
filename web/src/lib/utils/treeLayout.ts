import { stratify, tree as d3tree } from 'd3-hierarchy';
import type { EtymRelType, TreeEdge, TreeNode, TreeSlice } from '../types';

export const NODE_WIDTH = 120;
export const NODE_HEIGHT = 32;

const SIBLING_GAP = 24;
const ROW_HEIGHT = 64;
const PADDING = 16;

export interface PositionedNode extends TreeNode {
  x: number;
  y: number;
  isFocus: boolean;
}

export interface LayoutEdge {
  srcId: string;
  dstId: string;
  relTypes: EtymRelType[];
  sourceRefs: string[];
  kind: 'tree' | 'cross-link';
}

export interface ViewBox {
  minX: number;
  minY: number;
  width: number;
  height: number;
}

export interface TreeLayout {
  nodes: PositionedNode[];
  edges: LayoutEdge[];
  viewBox: ViewBox;
}

// Direct lineage relations outrank morphological decomposition when a
// converging node has more than one edge landing it at its own
// resolved depth, so the diagram's spine follows descent rather than
// word-part breakdown (ETYM-114). cognate/onomatopoeic have no rows
// in the loaded dataset and weren't in that ranking; placed last so
// the lookup stays exhaustive over EtymRelType.
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

interface MergedEdge {
  srcId: string;
  dstId: string;
  relTypes: EtymRelType[];
  sourceRefs: string[];
}

function mergeDuplicateEdges(edges: TreeEdge[]): MergedEdge[] {
  const byPair = new Map<string, MergedEdge>();
  for (const edge of edges) {
    const key = `${edge.srcId}:${edge.dstId}`;
    const existing = byPair.get(key);
    if (existing) {
      existing.relTypes.push(edge.relType);
      existing.sourceRefs.push(edge.sourceRef);
    } else {
      byPair.set(key, {
        srcId: edge.srcId,
        dstId: edge.dstId,
        relTypes: [edge.relType],
        sourceRefs: [edge.sourceRef],
      });
    }
  }
  return [...byPair.values()];
}

function bestRank(edge: MergedEdge): number {
  return Math.min(...edge.relTypes.map((r) => REL_TYPE_PRIORITY[r]));
}

function otherEnd(edge: MergedEdge, nodeId: string): string {
  return edge.srcId === nodeId ? edge.dstId : edge.srcId;
}

function towardFocusDepth(depth: number): number {
  return depth < 0 ? depth + 1 : depth - 1;
}

// For every non-focus node, picks the single edge that places it at
// its own resolved depth (ETYM-114: tie-broken by rel_type priority,
// then the neighboring node's id). Every other edge in this half --
// including one whose two endpoints sit at the same depth, which can
// never be either endpoint's placing edge -- is a cross-link.
function pickParentEdges(
  nodeIds: string[],
  focusId: string,
  depthOf: Map<string, number>,
  edges: MergedEdge[],
): { parentIdOf: Map<string, string>; crossLinks: MergedEdge[] } {
  const incident = new Map<string, MergedEdge[]>();
  for (const edge of edges) {
    for (const id of [edge.srcId, edge.dstId]) {
      const list = incident.get(id) ?? [];
      list.push(edge);
      incident.set(id, list);
    }
  }

  const parentIdOf = new Map<string, string>();
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
      parentIdOf.set(nodeId, focusId);
      continue;
    }
    parentIdOf.set(nodeId, otherEnd(chosen, nodeId));
    usedKeys.add(`${chosen.srcId}:${chosen.dstId}`);
  }

  const crossLinks = edges.filter(
    (edge) => !usedKeys.has(`${edge.srcId}:${edge.dstId}`),
  );
  return { parentIdOf, crossLinks };
}

interface StratifyDatum {
  id: string;
  parentId: string | null;
  headword: string;
}

// Lays out one half (every node with depth <= 0, or depth >= 0) as a
// strict tree rooted at the focus, then recenters it so the focus
// sits at x = 0 -- d3.tree() centers a root over its own children,
// not necessarily at x = 0, and both halves must agree on where the
// shared focus sits.
function layoutHalf(
  nodes: TreeNode[],
  focusId: string,
  parentIdOf: Map<string, string>,
): Map<string, { x: number; y: number }> {
  const data: StratifyDatum[] = nodes.map((node) => ({
    id: node.id,
    parentId: node.id === focusId ? null : parentIdOf.get(node.id)!,
    headword: node.headword,
  }));

  const root = stratify<StratifyDatum>()
    .id((d) => d.id)
    .parentId((d) => d.parentId)(data);

  root.sort((a, b) =>
    a.data.headword.localeCompare(b.data.headword, 'en'),
  );
  const positionedRoot = d3tree<StratifyDatum>().nodeSize([
    NODE_WIDTH + SIBLING_GAP,
    ROW_HEIGHT,
  ])(root);

  const offsetX = positionedRoot.x;
  const positions = new Map<string, { x: number; y: number }>();
  for (const node of positionedRoot.descendants()) {
    positions.set(node.data.id, { x: node.x - offsetX, y: node.y });
  }
  return positions;
}

export function layoutTree(slice: TreeSlice): TreeLayout {
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

  const ancestorPositions = layoutHalf(
    ancestorNodes,
    slice.focusId,
    ancestorPick.parentIdOf,
  );
  const descendantPositions = layoutHalf(
    descendantNodes,
    slice.focusId,
    descendantPick.parentIdOf,
  );

  const positioned: PositionedNode[] = slice.nodes.map((node) => {
    const raw =
      node.depth <= 0
        ? ancestorPositions.get(node.id)!
        : descendantPositions.get(node.id)!;
    const sign = node.depth <= 0 ? -1 : 1;
    const y = sign * raw.y;
    return {
      ...node,
      x: raw.x,
      // sign * 0 yields -0 for a depth-0 node in the negated
      // (ancestor) half; Object.is(-0, 0) is false, which fails
      // Vitest's toBe/toMatchObject against a plain 0, so normalize
      // back to positive zero.
      y: y === 0 ? 0 : y,
      isFocus: node.id === slice.focusId,
    };
  });

  const edgeKey = (e: MergedEdge) => `${e.srcId}:${e.dstId}`;
  const ancestorKeys = new Set(ancestorEdges.map(edgeKey));
  const descendantKeys = new Set(descendantEdges.map(edgeKey));
  const ancestorCrossLinkKeys = new Set(
    ancestorPick.crossLinks.map(edgeKey),
  );
  const descendantCrossLinkKeys = new Set(
    descendantPick.crossLinks.map(edgeKey),
  );

  const edges: LayoutEdge[] = mergedEdges.map((edge) => {
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

  const xs = positioned.map((n) => n.x);
  const ys = positioned.map((n) => n.y);
  const minX = Math.min(...xs) - NODE_WIDTH / 2 - PADDING;
  const maxX = Math.max(...xs) + NODE_WIDTH / 2 + PADDING;
  const minY = Math.min(...ys) - NODE_HEIGHT / 2 - PADDING;
  const maxY = Math.max(...ys) + NODE_HEIGHT / 2 + PADDING;

  return {
    nodes: positioned,
    edges,
    viewBox: { minX, minY, width: maxX - minX, height: maxY - minY },
  };
}
