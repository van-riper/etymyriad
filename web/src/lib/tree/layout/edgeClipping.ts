interface Point {
  x: number;
  y: number;
}

// Where a segment from `from` to `to` first touches the axis-aligned
// box of `boxWidth` x `boxHeight` centered on `to`, so a line drawn
// only as far as this point stops at the destination node's border
// instead of its center, leaving room for an arrowhead to render
// on top of it rather than underneath the node's opaque rect.
export function trimToBoxBoundary(
  from: Point,
  to: Point,
  boxWidth: number,
  boxHeight: number,
): Point {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  if (dx === 0 && dy === 0) return to;
  const tx = dx === 0 ? Infinity : boxWidth / 2 / Math.abs(dx);
  const ty = dy === 0 ? Infinity : boxHeight / 2 / Math.abs(dy);
  const t = Math.min(tx, ty);
  return { x: to.x - dx * t, y: to.y - dy * t };
}
