import { linkVertical } from 'd3-shape';

interface Point {
  x: number;
  y: number;
}

interface LinkDatum {
  source: Point;
  target: Point;
}

const treeLink = linkVertical<LinkDatum, Point>()
  .x((d) => d.x)
  .y((d) => d.y);

// An S-curve bezier between generations, replacing a straight line --
// d3-shape's default linkVertical curve, an S-shape through the
// vertical midpoint between src and dst.
export function treeEdgePath(src: Point, dst: Point): string {
  return treeLink({ source: src, target: dst })!;
}

// The same 4 control points linkVertical's curve draws through, so a
// label can sit on the curve's actual midpoint rather than the naive
// (src+dst)/2 average, which drifts off the curve whenever src.x !==
// dst.x.
function verticalControlPoints(
  p0: Point,
  p3: Point,
): [Point, Point, Point, Point] {
  const midY = (p0.y + p3.y) / 2;
  return [p0, { x: p0.x, y: midY }, { x: p3.x, y: midY }, p3];
}

export function cubicBezierMidpoint(
  p0: Point,
  p1: Point,
  p2: Point,
  p3: Point,
): Point {
  const at = (a: number, b: number, c: number, d: number) =>
    0.125 * a + 0.375 * b + 0.375 * c + 0.125 * d;
  return {
    x: at(p0.x, p1.x, p2.x, p3.x),
    y: at(p0.y, p1.y, p2.y, p3.y),
  };
}

export function treeEdgeMidpoint(src: Point, dst: Point): Point {
  const [p0, p1, p2, p3] = verticalControlPoints(src, dst);
  return cubicBezierMidpoint(p0, p1, p2, p3);
}
