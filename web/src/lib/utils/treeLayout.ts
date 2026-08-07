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
  // Only set for kind: 'cross-link' -- an SVG path `d` attribute
  // routed through the gap between rows (see routeCrossLinks below),
  // rather than a straight line that could cut through same-row
  // nodes it isn't connecting.
  path?: string;
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

// Cross-link routing: a 90-degree "bracket" path (down/up, across,
// down/up) through the gap between rows, instead of a straight line
// that can cut through other lines it isn't connecting.
// CROSS_LINK_CLEARANCE clears a same-row node's own half-height
// (NODE_HEIGHT / 2) with margin. Concurrent cross-links sharing a
// row/gap only need separate lanes (stacked further out by
// CROSS_LINK_LANE_STEP) when their spans actually overlap in x --
// two links whose spans don't overlap share the same lane instead of
// stacking unnecessarily (see assignLanes).
//
// A cross-link segment (a stem or the horizontal run) can still cross
// two kinds of line it doesn't connect to, and the two need different
// treatment depending on whether they meet at a point or run
// alongside each other:
//
// - A stem and a nearby lane's horizontal run, or a stem and a tree
//   edge that shares its node's x (most commonly a node's own edge to
//   its next-generation ancestor/descendant, which shares that node's
//   x whenever it's an only child), are collinear over a real range,
//   not just a point -- a bump can't visually separate them since the
//   line either side of the bump still sits exactly on top of the
//   obstacle. That stem instead dodges sideways for its whole run
//   (see collinearTreeOverlap), converging back onto the true node
//   position only at the end that must land exactly on a node.
// - A horizontal run crossing a tree edge (see the real example this
//   fixes: ETYM-161's follow-up) meets it at a single point, so a
//   small semicircular bridge -- the circuit-diagram convention for
//   "this wire hops over that one, they don't connect" -- is enough.
//   Always on the cross-link's own segment, never on the tree edge,
//   since lineage is the primary structure a cross-link is secondary
//   to.
// ponytail: cross-link-vs-cross-link bridging only looks within the
// same row/gap channel, not across channels, and a dodging stem isn't
// re-checked against other obstacles. Revisit with a real grid router
// if a denser tree shows either falling short.
const CROSS_LINK_CLEARANCE = NODE_HEIGHT / 2 + 8;
const CROSS_LINK_LANE_STEP = 16;
const CROSS_LINK_BRIDGE_RADIUS = 5;
const CROSS_LINK_DODGE = 10;

interface Point {
  x: number;
  y: number;
}

interface Segment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

// Whether a vertical stem at x, spanning (yFrom, yTo), runs alongside
// a tree edge that is itself vertical at the same x, for a real
// overlapping range (not just touching at one shared endpoint).
function collinearTreeOverlap(
  x: number,
  yFrom: number,
  yTo: number,
  treeObstacles: Segment[],
): boolean {
  const lo = Math.min(yFrom, yTo);
  const hi = Math.max(yFrom, yTo);
  return treeObstacles.some((obstacle) => {
    if (obstacle.x1 !== obstacle.x2 || obstacle.x1 !== x) return false;
    const oLo = Math.min(obstacle.y1, obstacle.y2);
    const oHi = Math.max(obstacle.y1, obstacle.y2);
    return Math.max(oLo, lo) < Math.min(oHi, hi);
  });
}

// Where `segment` crosses the horizontal line y, restricted to
// strictly inside both the segment's own y-span and (xLo, xHi).
function crossesHorizontalAt(
  segment: Segment,
  y: number,
  xLo: number,
  xHi: number,
): number | null {
  const { x1, y1, x2, y2 } = segment;
  if (y1 === y2) {
    if (y1 !== y) return null;
    const lo = Math.max(Math.min(x1, x2), xLo);
    const hi = Math.min(Math.max(x1, x2), xHi);
    return lo < hi ? (lo + hi) / 2 : null;
  }
  const t = (y - y1) / (y2 - y1);
  if (t <= 0 || t >= 1) return null;
  const x = x1 + t * (x2 - x1);
  return x > xLo && x < xHi ? x : null;
}

function crossLinkChannelKey(srcY: number, dstY: number): string {
  return srcY === dstY
    ? `row:${srcY}`
    : `gap:${Math.min(srcY, dstY)}:${Math.max(srcY, dstY)}`;
}

function crossLinkLaneY(srcY: number, dstY: number, lane: number): number {
  const sameRow = srcY === dstY;
  const base = sameRow ? srcY : (srcY + dstY) / 2;
  const sign = base >= 0 ? 1 : -1;
  const offset = sameRow ? CROSS_LINK_CLEARANCE : 0;
  return base + sign * (offset + lane * CROSS_LINK_LANE_STEP);
}

interface CrossLinkSpan {
  edge: LayoutEdge;
  minX: number;
  maxX: number;
}

// Minimum-lane ("minimum platforms") assignment: sorts spans by their
// left edge and reuses the first lane whose last-placed span ends
// before this one starts, opening a new lane only when every existing
// lane is still occupied at this x. Two links land in the same lane
// (and therefore the same horizontal line) only when doing so can
// never make their own segments overlap.
function assignLanes(spans: CrossLinkSpan[]): Map<LayoutEdge, number> {
  const sorted = [...spans].sort((a, b) => a.minX - b.minX || a.maxX - b.maxX);
  const laneEndX: number[] = [];
  const laneOf = new Map<LayoutEdge, number>();
  for (const span of sorted) {
    let lane = laneEndX.findIndex((endX) => endX <= span.minX);
    if (lane === -1) {
      lane = laneEndX.length;
      laneEndX.push(span.maxX);
    } else {
      laneEndX[lane] = span.maxX;
    }
    laneOf.set(span.edge, lane);
  }
  return laneOf;
}

// Every nearer lane (index < ownLane) whose span covers `x` -- a
// point where this stem, on its way out to its own lane, would
// otherwise cross that lane's horizontal run.
function laneCrossingsOnStem(
  x: number,
  ownLane: number,
  spansByLane: CrossLinkSpan[][],
  laneY: (lane: number) => number,
): number[] {
  const crossings: number[] = [];
  for (let lane = 0; lane < ownLane; lane++) {
    const hit = spansByLane[lane]?.some((s) => x > s.minX && x < s.maxX);
    if (hit) crossings.push(laneY(lane));
  }
  return crossings;
}

function treeCrossingsOnHorizontal(
  y: number,
  xFrom: number,
  xTo: number,
  treeObstacles: Segment[],
): number[] {
  const lo = Math.min(xFrom, xTo);
  const hi = Math.max(xFrom, xTo);
  const crossings: number[] = [];
  for (const obstacle of treeObstacles) {
    const x = crossesHorizontalAt(obstacle, y, lo, hi);
    if (x !== null) crossings.push(x);
  }
  return crossings;
}

// One straight run along a single axis (fixed = 'x' for a vertical
// stem, 'y' for the horizontal run), with a small semicircular bridge
// at each crossing so it visibly hops over whatever it crosses
// instead of touching it.
function runWithBridges(
  fixed: 'x' | 'y',
  fixedValue: number,
  from: number,
  to: number,
  crossings: number[],
): string {
  const direction = to >= from ? 1 : -1;
  const ordered = [...crossings].sort((a, b) => direction * (a - b));
  const point = (varying: number) =>
    fixed === 'x' ? `${fixedValue},${varying}` : `${varying},${fixedValue}`;
  let d = '';
  for (const v of ordered) {
    const enter = v - direction * CROSS_LINK_BRIDGE_RADIUS;
    const exit = v + direction * CROSS_LINK_BRIDGE_RADIUS;
    d += ` L ${point(enter)} A ${CROSS_LINK_BRIDGE_RADIUS},${CROSS_LINK_BRIDGE_RADIUS} 0 0 1 ${point(exit)}`;
  }
  d += ` L ${point(to)}`;
  return d;
}

// Assigns each cross-link edge a routed `path`: a bracket through the
// gap between rows, lanes assigned per row/gap so only genuinely
// overlapping links stack apart, and a bridge wherever a segment
// still has to cross a nearer lane's run or a tree edge.
function routeCrossLinks(
  edges: LayoutEdge[],
  nodeCenterById: Map<string, Point>,
): void {
  const treeObstacles: Segment[] = edges
    .filter((e) => e.kind === 'tree')
    .map((e) => {
      const src = nodeCenterById.get(e.srcId)!;
      const dst = nodeCenterById.get(e.dstId)!;
      return { x1: src.x, y1: src.y, x2: dst.x, y2: dst.y };
    });

  const groups = new Map<string, CrossLinkSpan[]>();
  for (const edge of edges) {
    if (edge.kind !== 'cross-link') continue;
    const src = nodeCenterById.get(edge.srcId);
    const dst = nodeCenterById.get(edge.dstId);
    if (!src || !dst) continue;
    const key = crossLinkChannelKey(src.y, dst.y);
    const group = groups.get(key) ?? [];
    group.push({
      edge,
      minX: Math.min(src.x, dst.x),
      maxX: Math.max(src.x, dst.x),
    });
    groups.set(key, group);
  }

  for (const [key, spans] of groups) {
    const [srcYRaw, dstYRaw] = key.startsWith('row:')
      ? [Number(key.slice(4)), Number(key.slice(4))]
      : (key.slice(4).split(':').map(Number) as [number, number]);
    const laneOf = assignLanes(spans);
    const spansByLane: CrossLinkSpan[][] = [];
    for (const span of spans) {
      const lane = laneOf.get(span.edge)!;
      if (!spansByLane[lane]) spansByLane[lane] = [];
      spansByLane[lane].push(span);
    }
    const laneY = (lane: number) => crossLinkLaneY(srcYRaw, dstYRaw, lane);

    for (const span of spans) {
      const { edge } = span;
      const src = nodeCenterById.get(edge.srcId)!;
      const dst = nodeCenterById.get(edge.dstId)!;
      const lane = laneOf.get(edge)!;
      const y = laneY(lane);

      // A dodging stem doesn't need re-checking against lane
      // crossings: it's already off the true node column, and the
      // lane spans below are computed against that column anyway.
      const srcDodges = collinearTreeOverlap(src.x, src.y, y, treeObstacles);
      const srcRunX = srcDodges ? src.x + CROSS_LINK_DODGE : src.x;
      const srcStem = srcDodges
        ? ` L ${srcRunX},${src.y} L ${srcRunX},${y}`
        : runWithBridges(
            'x',
            src.x,
            src.y,
            y,
            laneCrossingsOnStem(src.x, lane, spansByLane, laneY),
          );

      const dstDodges = collinearTreeOverlap(dst.x, y, dst.y, treeObstacles);
      const dstRunX = dstDodges ? dst.x + CROSS_LINK_DODGE : dst.x;
      const dstStem = dstDodges
        ? ` L ${dstRunX},${y} L ${dstRunX},${dst.y} L ${dst.x},${dst.y}`
        : runWithBridges(
            'x',
            dst.x,
            y,
            dst.y,
            laneCrossingsOnStem(dst.x, lane, spansByLane, laneY),
          );

      const horizontal = runWithBridges(
        'y',
        y,
        srcRunX,
        dstRunX,
        treeCrossingsOnHorizontal(y, srcRunX, dstRunX, treeObstacles),
      );
      edge.path = `M ${src.x},${src.y}${srcStem}${horizontal}${dstStem}`;
    }
  }
}

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
