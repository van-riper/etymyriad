interface Point {
  x: number;
  y: number;
}

// How far each control point leans toward the opposite endpoint's x,
// as a fraction of the total horizontal offset. 0 would put both
// control points directly above/below their own endpoint (d3-shape's
// linkVertical default), but then the curve's tangent AT the
// endpoint is always exactly vertical (p2.x === p3.x), so the
// arrowhead (marker orient="auto" reads the path's own tangent) always
// points straight down/up no matter how far the edge leans sideways,
// looking locked at a right angle against the curve's actual
// approach. Leaning the control points blends the end tangent toward
// the edge's real src-to-dst direction instead.
const END_TANGENT_LEAN = 0.3;

// An S-curve bezier between generations, replacing a straight line.
function verticalControlPoints(
  p0: Point,
  p3: Point,
): [Point, Point, Point, Point] {
  const dx = p3.x - p0.x;
  const midY = (p0.y + p3.y) / 2;
  return [
    p0,
    { x: p0.x + dx * END_TANGENT_LEAN, y: midY },
    { x: p3.x - dx * END_TANGENT_LEAN, y: midY },
    p3,
  ];
}

export function treeEdgePath(src: Point, dst: Point): string {
  const [p0, p1, p2, p3] = verticalControlPoints(src, dst);
  return `M${p0.x},${p0.y}C${p1.x},${p1.y},${p2.x},${p2.y},${p3.x},${p3.y}`;
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
