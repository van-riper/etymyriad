import { describe, expect, it } from 'vitest';
import { layoutTree } from './treeLayout';
import type { TreeSlice } from '../types';

describe('layoutTree', () => {
  it('positions a lone focus node at the origin', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        { id: 'f', langCode: 'en', headword: 'grandfather', depth: 0 },
      ],
      edges: [],
    };

    const layout = layoutTree(slice);

    expect(layout.nodes).toHaveLength(1);
    expect(layout.nodes[0]).toMatchObject({
      id: 'f',
      x: 0,
      y: 0,
      isFocus: true,
    });
    expect(layout.edges).toHaveLength(0);
    expect(layout.viewBox.width).toBeGreaterThan(0);
    expect(layout.viewBox.height).toBeGreaterThan(0);
  });

  it('stacks a linear ancestor chain directly above the focus, one row per generation', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        { id: 'f', langCode: 'en', headword: 'grandfather', depth: 0 },
        { id: 'a1', langCode: 'enm', headword: 'grandfadre', depth: -1 },
        { id: 'a2', langCode: 'ang', headword: 'ealdefæder', depth: -2 },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'a2', dstId: 'a1', relType: 'inherited', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get('f')).toMatchObject({ x: 0, y: 0 });
    expect(byId.get('a1')!.y).toBeLessThan(0);
    expect(byId.get('a2')!.y).toBeLessThan(byId.get('a1')!.y);
    expect(byId.get('a1')!.x).toBe(byId.get('f')!.x);
    expect(byId.get('a2')!.x).toBe(byId.get('f')!.x);

    expect(layout.edges).toHaveLength(2);
    expect(layout.edges.every((e) => e.kind === 'tree')).toBe(true);
  });

  it('mirrors descendants below the focus, sharing one focus at the origin', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        { id: 'f', langCode: 'en', headword: 'grandfather', depth: 0 },
        { id: 'a1', langCode: 'enm', headword: 'grandfadre', depth: -1 },
        { id: 'd1', langCode: 'fr', headword: 'grand-père', depth: 1 },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'f', dstId: 'd1', relType: 'borrowed', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(layout.nodes.filter((n) => n.id === 'f')).toHaveLength(1);
    expect(byId.get('f')).toMatchObject({ x: 0, y: 0 });
    expect(byId.get('a1')!.y).toBeLessThan(0);
    expect(byId.get('d1')!.y).toBeGreaterThan(0);
  });

  it('breaks a same-depth parent tie by rel_type priority, preferring lineage over morphology', () => {
    const slice: TreeSlice = {
      focusId: 'focus',
      nodes: [
        { id: 'focus', langCode: 'en', headword: 'focus', depth: 0 },
        { id: 'A', langCode: 'en', headword: 'a-word', depth: -1 },
        { id: 'B', langCode: 'en', headword: 'b-word', depth: -1 },
        { id: 'C', langCode: 'en', headword: 'c-word', depth: -2 },
      ],
      edges: [
        { srcId: 'A', dstId: 'focus', relType: 'derived', sourceRef: 'rA' },
        { srcId: 'B', dstId: 'focus', relType: 'derived', sourceRef: 'rB' },
        { srcId: 'C', dstId: 'A', relType: 'affix', sourceRef: 'rCA' },
        { srcId: 'C', dstId: 'B', relType: 'inherited', sourceRef: 'rCB' },
      ],
    };

    const layout = layoutTree(slice);
    const edgeCA = layout.edges.find(
      (e) => e.srcId === 'C' && e.dstId === 'A',
    );
    const edgeCB = layout.edges.find(
      (e) => e.srcId === 'C' && e.dstId === 'B',
    );

    expect(edgeCB?.kind).toBe('tree');
    expect(edgeCA?.kind).toBe('cross-link');
  });
});
