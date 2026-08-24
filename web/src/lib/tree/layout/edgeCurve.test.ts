import { describe, expect, it } from 'vitest';
import { treeEdgeMidpoint, treeEdgePath } from './edgeCurve';

// The lean fraction each control point advances toward the opposite
// endpoint's x, mirrored independently of the implementation so this
// file still catches a regression in the constant's value, not just
// in the arithmetic around it.
const END_TANGENT_LEAN = 0.3;

function leanedControlPoints(
  src: { x: number; y: number },
  dst: { x: number; y: number },
) {
  const dx = dst.x - src.x;
  const midY = (src.y + dst.y) / 2;
  return {
    p0: src,
    p1: { x: src.x + dx * END_TANGENT_LEAN, y: midY },
    p2: { x: dst.x - dx * END_TANGENT_LEAN, y: midY },
    p3: dst,
  };
}

// A path's `C` command endpoint is its last coordinate pair; its
// tangent there points from the 2nd control point to that endpoint.
function parseCubic(d: string) {
  const nums = d.match(/-?\d+\.?\d*/g)!.map(Number);
  return {
    p0: { x: nums[0], y: nums[1] },
    p1: { x: nums[2], y: nums[3] },
    p2: { x: nums[4], y: nums[5] },
    p3: { x: nums[6], y: nums[7] },
  };
}

describe('treeEdgePath', () => {
  it('renders a cubic bezier from src to dst', () => {
    const path = treeEdgePath({ x: 0, y: 0 }, { x: 40, y: 64 });
    expect(path).toMatch(/^M0,0C/);
    expect(path).toContain('40,64');
  });

  it("leans the end tangent toward the edge's real direction instead of locking it vertical", () => {
    const path = treeEdgePath({ x: 0, y: 0 }, { x: 40, y: 64 });
    const { p2, p3 } = parseCubic(path);
    // A purely vertical tangent would have p2.x === p3.x exactly --
    // the arrowhead (marker orient="auto") would then always point
    // straight down regardless of how far the edge leans sideways.
    expect(p2.x).not.toEqual(p3.x);
    // The lean is toward dst, not away from it or overshooting past
    // it.
    expect(p2.x).toBeGreaterThan(0);
    expect(p2.x).toBeLessThan(40);
  });

  it('keeps a perfectly vertical edge perfectly vertical', () => {
    const path = treeEdgePath({ x: 10, y: 0 }, { x: 10, y: 64 });
    const { p1, p2 } = parseCubic(path);
    expect(p1.x).toEqual(10);
    expect(p2.x).toEqual(10);
  });
});

describe('treeEdgeMidpoint', () => {
  it('is the exact midpoint for a straight vertical curve', () => {
    const mid = treeEdgeMidpoint({ x: 10, y: 0 }, { x: 10, y: 64 });
    expect(mid).toEqual({ x: 10, y: 32 });
  });

  it('matches the hand-computed cubic bezier at t=0.5 off-axis', () => {
    const src = { x: 0, y: 0 };
    const dst = { x: 40, y: 64 };
    const { p0, p1, p2, p3 } = leanedControlPoints(src, dst);
    const b = (a: number, b2: number, c: number, d: number) =>
      0.125 * a + 0.375 * b2 + 0.375 * c + 0.125 * d;
    const expected = {
      x: b(p0.x, p1.x, p2.x, p3.x),
      y: b(p0.y, p1.y, p2.y, p3.y),
    };
    expect(treeEdgeMidpoint(src, dst)).toEqual(expected);
  });
});
