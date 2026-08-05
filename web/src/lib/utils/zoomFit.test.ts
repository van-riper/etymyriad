import { describe, expect, it } from 'vitest';
import { computeFitTransform, FLOOR_SCALE } from './zoomFit';
import type { ViewBox } from './treeLayout';

describe('computeFitTransform', () => {
  it('scales a small tree up to fill the container, as before', () => {
    const viewBox: ViewBox = { minX: 0, minY: 0, width: 400, height: 300 };

    const transform = computeFitTransform(viewBox, 800, 600);

    expect(transform.k).toBe(2);
    expect(transform.x).toBeCloseTo(400 - 2 * 200);
    expect(transform.y).toBeCloseTo(300 - 2 * 150);
  });

  it('centers a viewBox that is not anchored at the origin', () => {
    const viewBox: ViewBox = { minX: -100, minY: -50, width: 400, height: 300 };

    const transform = computeFitTransform(viewBox, 800, 600);

    // Container center (400, 300) must map to the viewBox center
    // (100, 100) at scale k = 2.
    expect(transform.k).toBe(2);
    expect(transform.x).toBeCloseTo(400 - 2 * 100);
    expect(transform.y).toBeCloseTo(300 - 2 * 100);
  });

  it('clamps a large tree to the floor scale instead of shrinking further', () => {
    const viewBox: ViewBox = { minX: 0, minY: 0, width: 5000, height: 3000 };

    const transform = computeFitTransform(viewBox, 800, 600);

    expect(transform.k).toBe(FLOOR_SCALE);
  });
});
