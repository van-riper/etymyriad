import { describe, expect, it } from 'vitest';
import { assignTreePorts, portOffsets } from './edgePorts';
import type { LayoutEdge } from './types';

function treeEdge(srcId: number, dstId: number): LayoutEdge {
  return {
    srcId,
    dstId,
    relTypes: ['derived'],
    sourceRefs: ['r'],
  };
}

describe('portOffsets', () => {
  it('centers a single port', () => {
    expect(portOffsets(1, 100)).toEqual([0]);
  });

  it('spreads two ports symmetrically', () => {
    const offsets = portOffsets(2, 100);
    expect(offsets).toHaveLength(2);
    expect(offsets[0]).toBeCloseTo(-offsets[1]);
    expect(offsets[0]).toBeLessThan(offsets[1]);
  });

  it('spreads three ports evenly with the middle one centered', () => {
    const offsets = portOffsets(3, 100);
    expect(offsets[1]).toBeCloseTo(0);
    expect(offsets[2] - offsets[1]).toBeCloseTo(offsets[1] - offsets[0]);
  });

  it('keeps ports within a fraction of the given span', () => {
    const offsets = portOffsets(2, 100);
    expect(Math.abs(offsets[0])).toBeLessThan(50);
  });
});

describe('assignTreePorts', () => {
  it("leaves an only child's port at its parent's center", () => {
    const edges = [treeEdge(1, 2)];
    const nodeById = new Map([
      [1, { x: 0, y: 0, width: 120 }],
      [2, { x: 184, y: 0, width: 120 }],
    ]);
    const ports = assignTreePorts(edges, nodeById);
    expect(ports.get('1:2')).toEqual({ x: 60, y: 0 });
  });

  it('spreads three children in y-order across their parent', () => {
    const edges = [treeEdge(1, 3), treeEdge(1, 4), treeEdge(1, 5)];
    const nodeById = new Map([
      [1, { x: 0, y: 0, width: 120 }],
      [3, { x: 184, y: -56, width: 120 }],
      [4, { x: 184, y: 0, width: 120 }],
      [5, { x: 184, y: 56, width: 120 }],
    ]);
    const ports = assignTreePorts(edges, nodeById);
    const topY = ports.get('1:3')!.y;
    const midY = ports.get('1:4')!.y;
    const bottomY = ports.get('1:5')!.y;
    expect(topY).toBeLessThan(midY);
    expect(midY).toBeCloseTo(0);
    expect(midY).toBeLessThan(bottomY);
    // Every port sits on the parent's right border, not its center.
    for (const key of ['1:3', '1:4', '1:5']) {
      expect(ports.get(key)!.x).toEqual(60);
    }
  });
});
