import { describe, expect, it } from 'vitest';
import { treeEdgeMidpoint, treeEdgePath } from './edgeCurve';

describe('treeEdgePath', () => {
  it('renders a cubic bezier from src to dst', () => {
    const path = treeEdgePath({ x: 0, y: 0 }, { x: 40, y: 64 });
    expect(path).toMatch(/^M0,0C/);
    expect(path).toContain('40,64');
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
    const midY = (src.y + dst.y) / 2;
    const p0 = src;
    const p1 = { x: src.x, y: midY };
    const p2 = { x: dst.x, y: midY };
    const p3 = dst;
    const b = (a: number, b2: number, c: number, d: number) =>
      0.125 * a + 0.375 * b2 + 0.375 * c + 0.125 * d;
    const expected = {
      x: b(p0.x, p1.x, p2.x, p3.x),
      y: b(p0.y, p1.y, p2.y, p3.y),
    };
    expect(treeEdgeMidpoint(src, dst)).toEqual(expected);
  });
});
