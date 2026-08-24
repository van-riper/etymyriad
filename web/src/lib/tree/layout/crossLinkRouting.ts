import { trimToBoxBoundary } from './edgeClipping';
import { NODE_HEIGHT } from './nodeMetrics';
import type { LayoutEdge } from './types';

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
// - A horizontal run crossing a tree edge meets it at a single point,
//   so a small semicircular bridge -- the circuit-diagram convention
//   for "this wire hops over that one, they don't connect" -- is
//   enough. Always on the cross-link's own segment, never on the tree
//   edge, since lineage is the primary structure a cross-link is
//   secondary to.
// ponytail: cross-link-vs-cross-link bridging only looks within the
// same row/gap channel, not across channels, and a dodging stem isn't
// re-checked against other obstacles. Revisit with a real grid router
// if a denser tree shows either falling short.
const CROSS_LINK_CLEARANCE = NODE_HEIGHT / 2 + 8;
const CROSS_LINK_LANE_STEP = 16;
const CROSS_LINK_BRIDGE_RADIUS = 5;
const CROSS_LINK_DODGE = 10;
// Rounds only the bracket's 2 structural elbows (stem into the
// horizontal run, and back out), not the dodge sub-corners or bridge
// arcs -- a full grid-router rewrite is the earmarked next step if a
// denser tree needs more than this (see the file-level ponytail note
// above), not this pass.
const CORNER_RADIUS = 6;

interface Point {
  x: number;
  y: number;
  width: number;
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

// Clamped to half of each adjoining segment so a very short stem or
// horizontal run can't make the fillet overshoot its own segment.
function elbowRadius(
  adjoiningLength: number,
  horizontalLength: number,
): number {
  if (horizontalLength === 0) return 0;
  return Math.min(CORNER_RADIUS, adjoiningLength / 2, horizontalLength / 2);
}

interface XY {
  x: number;
  y: number;
}

// The midpoint by arc length of the bracket's own waypoints -- src,
// the two structural corners, and dst's trimmed approach -- ignoring
// the small fillet/bridge/dodge deviations from that straight-segment
// shape (their radii are small relative to a typical span).
function polylineMidpoint(points: XY[]): XY {
  const segmentLengths = points
    .slice(1)
    .map((p, i) => Math.hypot(p.x - points[i].x, p.y - points[i].y));
  const total = segmentLengths.reduce((sum, len) => sum + len, 0);
  if (total === 0) return points[0];
  let remaining = total / 2;
  for (let i = 0; i < segmentLengths.length; i++) {
    if (remaining <= segmentLengths[i]) {
      const t = segmentLengths[i] === 0 ? 0 : remaining / segmentLengths[i];
      const from = points[i];
      const to = points[i + 1];
      return {
        x: from.x + t * (to.x - from.x),
        y: from.y + t * (to.y - from.y),
      };
    }
    remaining -= segmentLengths[i];
  }
  return points[points.length - 1];
}

// Assigns each cross-link edge a routed `path`: a bracket through the
// gap between rows, lanes assigned per row/gap so only genuinely
// overlapping links stack apart, and a bridge wherever a segment
// still has to cross a nearer lane's run or a tree edge.
export function routeCrossLinks(
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

      const dstDodges = collinearTreeOverlap(dst.x, y, dst.y, treeObstacles);
      const dstRunX = dstDodges ? dst.x + CROSS_LINK_DODGE : dst.x;
      // The final approach into dst is always axis-aligned (this
      // bracket router only ever arrives vertically or, when dodging,
      // horizontally), so trimming it to the node's border -- rather
      // than its center -- leaves room for an arrowhead to render on
      // top of the path instead of underneath the node's opaque rect.
      const dstApproach = dstDodges
        ? { x: dstRunX, y: dst.y }
        : { x: dst.x, y };
      const dstTrim = trimToBoxBoundary(
        dstApproach,
        { x: dst.x, y: dst.y },
        dst.width,
        NODE_HEIGHT,
      );

      // The 2 structural elbows -- src stem into the horizontal run,
      // and the horizontal run back out into dst's stem -- get a
      // small quadratic fillet instead of a sharp right angle. Both
      // are always vertical-in/horizontal-out (or the reverse): a
      // dodge only ever shifts a stem's x, so its final approach into
      // either corner is still a plain vertical run.
      const hLen = Math.abs(dstRunX - srcRunX);
      const hDir = dstRunX >= srcRunX ? 1 : -1;
      const r1 = elbowRadius(Math.abs(y - src.y), hLen);
      const vDir1 = y >= src.y ? 1 : -1;
      const srcCornerStopY = y - vDir1 * r1;
      const horizontalStartX = srcRunX + hDir * r1;

      const r2 = elbowRadius(Math.abs(dst.y - y), hLen);
      const vDir2 = dst.y >= y ? 1 : -1;
      const horizontalEndX = dstRunX - hDir * r2;
      const dstCornerStopY = y + vDir2 * r2;

      const srcStem = srcDodges
        ? ` L ${srcRunX},${src.y} L ${srcRunX},${srcCornerStopY}`
        : runWithBridges(
            'x',
            src.x,
            src.y,
            srcCornerStopY,
            laneCrossingsOnStem(src.x, lane, spansByLane, laneY),
          );
      const srcFillet =
        r1 > 0 ? ` Q ${srcRunX},${y} ${horizontalStartX},${y}` : '';

      const horizontal = runWithBridges(
        'y',
        y,
        horizontalStartX,
        horizontalEndX,
        treeCrossingsOnHorizontal(y, srcRunX, dstRunX, treeObstacles),
      );
      const dstFillet =
        r2 > 0 ? ` Q ${dstRunX},${y} ${dstRunX},${dstCornerStopY}` : '';

      const dstStem = dstDodges
        ? ` L ${dstRunX},${dst.y} L ${dstTrim.x},${dstTrim.y}`
        : runWithBridges(
            'x',
            dst.x,
            dstCornerStopY,
            dstTrim.y,
            laneCrossingsOnStem(dst.x, lane, spansByLane, laneY),
          );

      edge.path = `M ${src.x},${src.y}${srcStem}${srcFillet}${horizontal}${dstFillet}${dstStem}`;
      edge.labelPosition = polylineMidpoint([
        { x: src.x, y: src.y },
        { x: srcRunX, y },
        { x: dstRunX, y },
        dstTrim,
      ]);
    }
  }
}
