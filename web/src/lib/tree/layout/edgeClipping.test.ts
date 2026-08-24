import { describe, expect, it } from 'vitest';
import { trimToBoxBoundary } from './edgeClipping';

describe('trimToBoxBoundary', () => {
  it('trims a horizontal approach to the box edge nearest the source', () => {
    const point = trimToBoxBoundary({ x: 0, y: 0 }, { x: 100, y: 0 }, 20, 20);
    expect(point).toEqual({ x: 90, y: 0 });
  });

  it('trims a vertical approach to the box edge nearest the source', () => {
    const point = trimToBoxBoundary({ x: 0, y: 0 }, { x: 0, y: 100 }, 20, 10);
    expect(point).toEqual({ x: 0, y: 95 });
  });

  it('trims a diagonal approach to whichever edge it reaches first', () => {
    const point = trimToBoxBoundary({ x: 0, y: 0 }, { x: 100, y: 50 }, 20, 10);
    expect(point).toEqual({ x: 90, y: 45 });
  });

  it('is a no-op when the two points coincide', () => {
    const point = trimToBoxBoundary({ x: 5, y: 5 }, { x: 5, y: 5 }, 20, 10);
    expect(point).toEqual({ x: 5, y: 5 });
  });
});
