import { stratify, tree as d3tree } from 'd3-hierarchy';
import type { EtymRelType, TreeEdge, TreeNode, TreeSlice } from '../types';

export const NODE_WIDTH = 120;
export const NODE_HEIGHT = 32;

const SIBLING_GAP = 24;
const ROW_HEIGHT = 64;
const PADDING = 16;

// A massive tree's node-noise comes from breadth (one node with
// hundreds of children), not depth, which is already bounded
// elsewhere. Capping direct children per parent keeps layout compute
// bounded by fan-out width, not by how many nodes the slice holds
// overall, since an overflowed child's whole subtree is skipped
// rather than laid out and hidden.
//
// 10 fits comfortably across a typical desktop viewport
// (NODE_WIDTH + SIBLING_GAP px per sibling) before any horizontal
// scroll is needed to reach the "+N more" affordance.
export const MAX_SIBLINGS_PER_PARENT = 10;

const OVERFLOW_ID_SUFFIX = '::overflow';

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

// A "+N more" affordance standing in for a parent's overflowed
// children. Clicking it (via an expanded parent id) reveals the rest;
// see TreeDiagram.svelte.
export interface OverflowNode {
  parentId: string;
  count: number;
  x: number;
  y: number;
}

export interface TreeLayout {
  nodes: PositionedNode[];
  edges: LayoutEdge[];
  overflow: OverflowNode[];
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
): {
  parentIdOf: Map<string, string>;
  parentEdgeRankOf: Map<string, number>;
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
    usedKeys.add(`${chosen.srcId}:${chosen.dstId}`);
  }

  const crossLinks = edges.filter(
    (edge) => !usedKeys.has(`${edge.srcId}:${edge.dstId}`),
  );
  return { parentIdOf, parentEdgeRankOf, crossLinks };
}

interface StratifyDatum {
  id: string;
  parentId: string | null;
  headword: string;
  isOverflow: boolean;
}

interface CoreSelection {
  coreIds: Set<string>;
  overflowByParent: Map<string, number>;
}

// BFS from the focus over this half's resolved parent/child edges,
// keeping at most MAX_SIBLINGS_PER_PARENT children per parent unless
// that parent is expanded. Kept children are the most etymologically
// relevant ones (their placing edge's rel_type priority, the same
// ranking pickParentEdges itself uses), alphabetical order only
// breaking ties within a tier, so a wide fan-out surfaces direct
// lineage over cognate/derived noise instead of an arbitrary
// alphabetical slice. An overflowed child's entire subtree is never
// visited, so the core, and therefore layoutHalf's stratify/tree call
// below, stays bounded by fan-out width rather than by how many nodes
// this half holds in total.
function selectCore(
  nodes: TreeNode[],
  focusId: string,
  parentIdOf: Map<string, string>,
  parentEdgeRankOf: Map<string, number>,
  expandedParents: ReadonlySet<string>,
): CoreSelection {
  const childrenByParent = new Map<string, TreeNode[]>();
  for (const node of nodes) {
    if (node.id === focusId) continue;
    const parentId = parentIdOf.get(node.id)!;
    const children = childrenByParent.get(parentId) ?? [];
    children.push(node);
    childrenByParent.set(parentId, children);
  }

  const coreIds = new Set<string>([focusId]);
  const overflowByParent = new Map<string, number>();
  const queue = [focusId];
  while (queue.length > 0) {
    const parentId = queue.shift()!;
    const children = childrenByParent.get(parentId) ?? [];
    children.sort((a, b) => {
      const rankDiff =
        (parentEdgeRankOf.get(a.id) ?? Infinity) -
        (parentEdgeRankOf.get(b.id) ?? Infinity);
      if (rankDiff !== 0) return rankDiff;
      return a.headword.localeCompare(b.headword, 'en');
    });
    const kept = expandedParents.has(parentId)
      ? children
      : children.slice(0, MAX_SIBLINGS_PER_PARENT);
    if (kept.length < children.length) {
      overflowByParent.set(parentId, children.length - kept.length);
    }
    for (const child of kept) {
      coreIds.add(child.id);
      queue.push(child.id);
    }
  }

  return { coreIds, overflowByParent };
}

interface HalfLayout {
  positions: Map<string, { x: number; y: number }>;
  overflow: OverflowNode[];
}

// Lays out one half (every node with depth <= 0, or depth >= 0) as a
// strict tree rooted at the focus, then recenters it so the focus
// sits at x = 0 -- d3.tree() centers a root over its own children,
// not necessarily at x = 0, and both halves must agree on where the
// shared focus sits. Only the core selected above is fed to
// stratify/tree; a "+N more" marker takes each overflowed parent's
// place as one extra child, so d3 reserves it a slot the same way it
// would a real sibling.
function layoutHalf(
  nodes: TreeNode[],
  focusId: string,
  parentIdOf: Map<string, string>,
  core: CoreSelection,
): HalfLayout {
  const data: StratifyDatum[] = nodes
    .filter((node) => core.coreIds.has(node.id))
    .map((node) => ({
      id: node.id,
      parentId: node.id === focusId ? null : parentIdOf.get(node.id)!,
      headword: node.headword,
      isOverflow: false,
    }));
  for (const parentId of core.overflowByParent.keys()) {
    data.push({
      id: `${parentId}${OVERFLOW_ID_SUFFIX}`,
      parentId,
      headword: '',
      isOverflow: true,
    });
  }

  const root = stratify<StratifyDatum>()
    .id((d) => d.id)
    .parentId((d) => d.parentId)(data);

  root.sort((a, b) => {
    // An overflow marker isn't a real headword, so it always sorts
    // after its parent's real (kept) children, however they collate.
    if (a.data.isOverflow) return 1;
    if (b.data.isOverflow) return -1;
    return a.data.headword.localeCompare(b.data.headword, 'en');
  });
  const positionedRoot = d3tree<StratifyDatum>().nodeSize([
    NODE_WIDTH + SIBLING_GAP,
    ROW_HEIGHT,
  ])(root);

  const offsetX = positionedRoot.x;
  const positions = new Map<string, { x: number; y: number }>();
  const overflow: OverflowNode[] = [];
  for (const node of positionedRoot.descendants()) {
    const x = node.x - offsetX;
    if (node.data.isOverflow) {
      const parentId = node.data.parentId!;
      overflow.push({
        parentId,
        count: core.overflowByParent.get(parentId)!,
        x,
        y: node.y,
      });
    } else {
      positions.set(node.data.id, { x, y: node.y });
    }
  }
  return { positions, overflow };
}

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

  const ancestorCore = selectCore(
    ancestorNodes,
    slice.focusId,
    ancestorPick.parentIdOf,
    ancestorPick.parentEdgeRankOf,
    expandedParents,
  );
  const descendantCore = selectCore(
    descendantNodes,
    slice.focusId,
    descendantPick.parentIdOf,
    descendantPick.parentEdgeRankOf,
    expandedParents,
  );

  const ancestorHalf = layoutHalf(
    ancestorNodes,
    slice.focusId,
    ancestorPick.parentIdOf,
    ancestorCore,
  );
  const descendantHalf = layoutHalf(
    descendantNodes,
    slice.focusId,
    descendantPick.parentIdOf,
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
      };
    });

  const overflow: OverflowNode[] = [
    ...ancestorHalf.overflow.map((o) => ({ ...o, y: signY(o.y, -1) })),
    ...descendantHalf.overflow.map((o) => ({ ...o, y: signY(o.y, 1) })),
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

  const xs = [...positioned.map((n) => n.x), ...overflow.map((o) => o.x)];
  const ys = [...positioned.map((n) => n.y), ...overflow.map((o) => o.y)];
  const minX = Math.min(...xs) - NODE_WIDTH / 2 - PADDING;
  const maxX = Math.max(...xs) + NODE_WIDTH / 2 + PADDING;
  const minY = Math.min(...ys) - NODE_HEIGHT / 2 - PADDING;
  const maxY = Math.max(...ys) + NODE_HEIGHT / 2 + PADDING;

  return {
    nodes: positioned,
    edges,
    overflow,
    viewBox: { minX, minY, width: maxX - minX, height: maxY - minY },
  };
}
