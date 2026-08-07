import { describe, expect, it } from 'vitest';
import { CEILING_SCALE, computeFitTransform, FLOOR_SCALE } from './zoomFit';
import { NODE_HEIGHT, NODE_WIDTH, type ViewBox } from './treeLayout';

describe('computeFitTransform', () => {
  it('scales a small tree up to fill the container, as before', () => {
    const viewBox: ViewBox = { minX: 0, minY: 0, width: 400, height: 300 };

    const transform = computeFitTransform(viewBox, 800, 600);

    expect(transform.k).toBe(2);
    expect(transform.x).toBeCloseTo(400 - 2 * 200);
    expect(transform.y).toBeCloseTo(300 - 2 * 150);
    expect(transform.clamped).toBe(false);
  });

  it('centers a viewBox that is not anchored at the origin', () => {
    const viewBox: ViewBox = { minX: -100, minY: -50, width: 400, height: 300 };

    const transform = computeFitTransform(viewBox, 800, 600);

    // Container center (400, 300) must map to the viewBox center
    // (100, 100) at scale k = 2.
    expect(transform.k).toBe(2);
    expect(transform.x).toBeCloseTo(400 - 2 * 100);
    expect(transform.y).toBeCloseTo(300 - 2 * 100);
    expect(transform.clamped).toBe(false);
  });

  it('clamps a large tree to the floor scale instead of shrinking further', () => {
    const viewBox: ViewBox = { minX: 0, minY: 0, width: 5000, height: 3000 };

    const transform = computeFitTransform(viewBox, 800, 600);

    expect(transform.k).toBe(FLOOR_SCALE);
    expect(transform.clamped).toBe(true);
  });

  it('clamps a tiny tree to the ceiling scale instead of growing unbounded', () => {
    const viewBox: ViewBox = { minX: 0, minY: 0, width: 40, height: 30 };

    const transform = computeFitTransform(viewBox, 800, 600);

    expect(transform.k).toBe(CEILING_SCALE);
    expect(transform.clamped).toBe(false);
  });

  it('keeps a two-node tree near its native node size in a large viewport', () => {
    // A real two-node vertical chain's viewBox (treeLayout.ts's
    // padding/row-height math), placed in a full-desktop-sized
    // container -- the raw fit ratio alone would be ~7x here, well
    // past legible before any ceiling is applied.
    const viewBox: ViewBox = { minX: -76, minY: -32, width: 152, height: 128 };

    const transform = computeFitTransform(viewBox, 1600, 900);

    expect(transform.k).toBe(CEILING_SCALE);
    expect(transform.k * NODE_WIDTH).toBeLessThanOrEqual(2 * NODE_WIDTH);
    expect(transform.k * NODE_HEIGHT).toBeLessThanOrEqual(2 * NODE_HEIGHT);
    expect(transform.clamped).toBe(false);
  });
});
