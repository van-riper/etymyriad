import { describe, expect, it } from 'vitest';
import { assignTreePorts, portOffsets } from './edgePorts';
import type { LayoutEdge } from './types';

function treeEdge(srcId: string, dstId: string): LayoutEdge {
  return {
    srcId,
    dstId,
    relTypes: ['derived'],
    sourceRefs: ['r'],
    kind: 'tree',
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
    const edges = [treeEdge('p', 'a')];
    const nodeById = new Map([
      ['p', { x: 0, y: 0, width: 120 }],
      ['a', { x: 0, y: 64, width: 120 }],
    ]);
    const ports = assignTreePorts(edges, nodeById);
    expect(ports.get('p:a')).toEqual({ x: 0, y: 16 });
  });

  it('spreads three children in x-order across their parent', () => {
    const edges = [
      treeEdge('p', 'left'),
      treeEdge('p', 'mid'),
      treeEdge('p', 'right'),
    ];
    const nodeById = new Map([
      ['p', { x: 0, y: 0, width: 120 }],
      ['left', { x: -80, y: 64, width: 120 }],
      ['mid', { x: 0, y: 64, width: 120 }],
      ['right', { x: 80, y: 64, width: 120 }],
    ]);
    const ports = assignTreePorts(edges, nodeById);
    const leftX = ports.get('p:left')!.x;
    const midX = ports.get('p:mid')!.x;
    const rightX = ports.get('p:right')!.x;
    expect(leftX).toBeLessThan(midX);
    expect(midX).toBeCloseTo(0);
    expect(midX).toBeLessThan(rightX);
    // Every port sits on the parent's bottom border, not its center.
    for (const key of ['p:left', 'p:mid', 'p:right']) {
      expect(ports.get(key)!.y).toEqual(16);
    }
  });

  it('ignores cross-link edges', () => {
    const edges: LayoutEdge[] = [
      {
        srcId: 'p',
        dstId: 'a',
        relTypes: ['cognate'],
        sourceRefs: ['r'],
        kind: 'cross-link',
      },
    ];
    const nodeById = new Map([
      ['p', { x: 0, y: 0, width: 120 }],
      ['a', { x: 0, y: 64, width: 120 }],
    ]);
    expect(assignTreePorts(edges, nodeById).size).toBe(0);
  });
});
