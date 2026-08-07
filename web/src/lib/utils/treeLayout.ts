import { stratify, tree as d3tree } from 'd3-hierarchy';
import { displayHeadword } from './headword';
import type { EtymRelType, TreeEdge, TreeNode, TreeSlice } from '../types';

// The minimum/default node width -- a node's rendered box never
// shrinks below this, even when its label is short enough to fit in
// less space (see widthForLabel below).
export const NODE_WIDTH = 120;
export const NODE_HEIGHT = 32;

// Matches TreeDiagram.svelte's `.node rect` stroke-width. A stroke
// straddles its path, so it adds this much to the rendered bounding
// box on top of the rect's own width/height -- callers measuring a
// rendered node (e.g. via getBoundingClientRect) must account for it.
export const NODE_STROKE_WIDTH = 1;

const SIBLING_GAP = 24;
const ROW_HEIGHT = 64;
const PADDING = 16;

// The rendered font is the page's default sans-serif at 0.75rem/12px
// (TreeDiagram.svelte's `.node text` rule sets no font-family). 7px
// is calibrated against a real long non-Latin headword rendered in a
// browser (a Cyrillic label needed ~6.7px/char; plain Latin needs
// less), not just a Latin-only guess -- the dataset's Indo-European
// scope spans several scripts (Cyrillic, Greek, diacritic-heavy
// reconstructed Latin, etc.), not only Latin.
// ponytail: naive per-character average, not a real glyph
// measurement -- retune this constant, or measure for real via
// canvas/getBBox once available, if visual QA on another script shows
// systematic over/under-sizing.
const AVG_CHAR_WIDTH_PX = 7;

function composeLabel(node: TreeNode): string {
  return `${displayHeadword(node.headword, node.isReconstructed)} (${node.langCode})`;
}

export function widthForLabel(label: string): number {
  return Math.max(NODE_WIDTH, Math.ceil(label.length * AVG_CHAR_WIDTH_PX));
}

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
  label: string;
  width: number;
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
// children. Clicking it (via an expanded parent id) reveals whatever
// is already present in `slice.nodes`; if `count` exceeds what's
// present, the rest was never fetched at all (ETYM-144) and the
// click must fetch it first -- see TreeDiagram.svelte.
export interface OverflowNode {
  parentId: string;
  direction: 'ancestor' | 'descendant';
  count: number;
  x: number;
  y: number;
  label: string;
  width: number;
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
  pieceOrders: Array<number | null>;
}

function mergeDuplicateEdges(edges: TreeEdge[]): MergedEdge[] {
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

interface StratifyDatum {
  id: string;
  parentId: string | null;
  headword: string;
  isOverflow: boolean;
  pieceOrder: number | null;
  label: string;
  width: number;
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
//
// serverOverflowByParent (ETYM-144) reports children the server never
// fetched at all -- capped during the walk itself, not just at
// render. It adds to the badge count regardless of expandedParents,
// since "already showing everything present" and "more exists but
// hasn't been fetched yet" are independent facts.
function selectCore(
  nodes: TreeNode[],
  focusId: string,
  parentIdOf: Map<string, string>,
  parentEdgeRankOf: Map<string, number>,
  expandedParents: ReadonlySet<string>,
  serverOverflowByParent: ReadonlyMap<string, number>,
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
    const overflow =
      children.length -
      kept.length +
      (serverOverflowByParent.get(parentId) ?? 0);
    if (overflow > 0) {
      overflowByParent.set(parentId, overflow);
    }
    for (const child of kept) {
      coreIds.add(child.id);
      queue.push(child.id);
    }
  }

  return { coreIds, overflowByParent };
}

// Omits `direction`, which the caller only knows once both halves
// have been laid out (see layoutTree).
type UndirectedOverflow = Omit<OverflowNode, 'direction'>;

interface PositionedDatum {
  x: number;
  y: number;
  label: string;
  width: number;
}

interface HalfLayout {
  positions: Map<string, PositionedDatum>;
  overflow: UndirectedOverflow[];
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
  parentEdgePieceOrderOf: Map<string, number | null>,
  core: CoreSelection,
): HalfLayout {
  const data: StratifyDatum[] = nodes
    .filter((node) => core.coreIds.has(node.id))
    .map((node) => {
      const label = composeLabel(node);
      return {
        id: node.id,
        parentId: node.id === focusId ? null : parentIdOf.get(node.id)!,
        headword: node.headword,
        isOverflow: false,
        pieceOrder: parentEdgePieceOrderOf.get(node.id) ?? null,
        label,
        width: widthForLabel(label),
      };
    });
  for (const [parentId, count] of core.overflowByParent) {
    const label = `+${count} more`;
    data.push({
      id: `${parentId}${OVERFLOW_ID_SUFFIX}`,
      parentId,
      headword: '',
      isOverflow: true,
      pieceOrder: null,
      label,
      width: widthForLabel(label),
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
    // Siblings that are composition pieces of their shared parent (a
    // prefix/root/suffix decomposition) order the way they occur in
    // that word, not alphabetically -- grouped ahead of any sibling
    // that isn't a piece at all (e.g. a cognate/inherited lineage
    // edge to the same parent), rather than interleaving by headword,
    // since comparing a piece to a non-piece by headword alone isn't
    // transitive and can silently reorder two pieces relative to each
    // other depending on where a third, unrelated sibling falls.
    const orderA = a.data.pieceOrder;
    const orderB = b.data.pieceOrder;
    if (orderA == null && orderB != null) return 1;
    if (orderA != null && orderB == null) return -1;
    if (orderA != null && orderB != null && orderA !== orderB) {
      return orderA - orderB;
    }
    return a.data.headword.localeCompare(b.data.headword, 'en');
  });
  // nodeSize's x-unit is 1, so separation()'s return value is read
  // directly as the pixel gap between adjacent node centers -- letting
  // it vary per node pair instead of the fixed NODE_WIDTH + SIBLING_GAP
  // this replaces. The (avgWidth + GAP) * multiplier shape (not just
  // multiplying the gap) is what preserves the old fixed-width
  // spacing exactly when both nodes sit at the floor width: d3's old
  // default separation (1 for siblings, 2 for cousins) times the old
  // nodeSize[0] gave 144/288 at the floor; this formula gives the same
  // 144/288 there, and now scales with each node's own width beyond it.
  const positionedRoot = d3tree<StratifyDatum>()
    .nodeSize([1, ROW_HEIGHT])
    .separation((a, b) => {
      const avgWidth = (a.data.width + b.data.width) / 2;
      const multiplier = a.parent === b.parent ? 1 : 2;
      return (avgWidth + SIBLING_GAP) * multiplier;
    })(root);

  const offsetX = positionedRoot.x;
  const positions = new Map<string, PositionedDatum>();
  const overflow: UndirectedOverflow[] = [];
  for (const node of positionedRoot.descendants()) {
    const x = node.x - offsetX;
    if (node.data.isOverflow) {
      const parentId = node.data.parentId!;
      overflow.push({
        parentId,
        count: core.overflowByParent.get(parentId)!,
        x,
        y: node.y,
        label: node.data.label,
        width: node.data.width,
      });
    } else {
      positions.set(node.data.id, {
        x,
        y: node.y,
        label: node.data.label,
        width: node.data.width,
      });
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
