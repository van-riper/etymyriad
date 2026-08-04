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

  it('collapses duplicate edges between the same node pair into one line', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        { id: 'f', langCode: 'en', headword: 'father', depth: 0 },
        { id: 'a1', langCode: 'ine-pro', headword: 'peh₂-', depth: -1 },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'a1', dstId: 'f', relType: 'root', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);

    expect(layout.edges).toHaveLength(1);
    expect(layout.edges[0].kind).toBe('tree');
    expect(layout.edges[0].relTypes.sort()).toEqual(['inherited', 'root']);
    expect(layout.edges[0].sourceRefs.sort()).toEqual(['r1', 'r2']);
  });

  it('classifies the real grandfather/father/peh₂- diamond correctly', () => {
    // ETYM-114's concrete example: grandfather has a direct affix
    // edge to father and a direct root edge to peh₂-; father also has
    // a direct root edge to that same peh₂-. treeSlice already
    // resolved peh₂- to its shortest depth (-1, direct), so both
    // father and peh₂- land at depth -1 here -- the peh₂--father edge
    // connects two same-depth nodes and can be neither's placing edge.
    const slice: TreeSlice = {
      focusId: 'gf',
      nodes: [
        { id: 'gf', langCode: 'en', headword: 'grandfather', depth: 0 },
        { id: 'father', langCode: 'en', headword: 'father', depth: -1 },
        { id: 'peh2', langCode: 'ine-pro', headword: 'peh₂-', depth: -1 },
      ],
      edges: [
        { srcId: 'father', dstId: 'gf', relType: 'affix', sourceRef: 'r1' },
        { srcId: 'peh2', dstId: 'gf', relType: 'root', sourceRef: 'r2' },
        {
          srcId: 'peh2',
          dstId: 'father',
          relType: 'root',
          sourceRef: 'r3',
        },
      ],
    };

    const layout = layoutTree(slice);

    expect(layout.edges).toHaveLength(3);
    const byPair = new Map(
      layout.edges.map((e) => [`${e.srcId}:${e.dstId}`, e]),
    );
    expect(byPair.get('father:gf')?.kind).toBe('tree');
    expect(byPair.get('peh2:gf')?.kind).toBe('tree');
    expect(byPair.get('peh2:father')?.kind).toBe('cross-link');
  });

  it('orders same-generation siblings alphabetically by headword', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        { id: 'f', langCode: 'en', headword: 'focus', depth: 0 },
        { id: 'z', langCode: 'en', headword: 'zeta', depth: -1 },
        { id: 'a', langCode: 'en', headword: 'alpha', depth: -1 },
        { id: 'm', langCode: 'en', headword: 'mid', depth: -1 },
      ],
      edges: [
        { srcId: 'z', dstId: 'f', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'a', dstId: 'f', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'm', dstId: 'f', relType: 'derived', sourceRef: 'r3' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get('a')!.x).toBeLessThan(byId.get('m')!.x);
    expect(byId.get('m')!.x).toBeLessThan(byId.get('z')!.x);
  });

  it('scales the viewBox with tree width and depth', () => {
    const narrow: TreeSlice = {
      focusId: 'f',
      nodes: [
        { id: 'f', langCode: 'en', headword: 'focus', depth: 0 },
        { id: 'a1', langCode: 'en', headword: 'a1', depth: -1 },
      ],
      edges: [{ srcId: 'a1', dstId: 'f', relType: 'derived', sourceRef: 'r' }],
    };
    const wide: TreeSlice = {
      focusId: 'f',
      nodes: [
        { id: 'f', langCode: 'en', headword: 'focus', depth: 0 },
        { id: 'a1', langCode: 'en', headword: 'a1', depth: -1 },
        { id: 'a2', langCode: 'en', headword: 'a2', depth: -1 },
        { id: 'a3', langCode: 'en', headword: 'a3', depth: -1 },
        { id: 'a4', langCode: 'en', headword: 'a4', depth: -1 },
        { id: 'a5', langCode: 'en', headword: 'a5', depth: -1 },
      ],
      edges: [1, 2, 3, 4, 5].map((n) => ({
        srcId: `a${n}`,
        dstId: 'f',
        relType: 'derived' as const,
        sourceRef: `r${n}`,
      })),
    };
    const shallow = narrow;
    const deep: TreeSlice = {
      focusId: 'f',
      nodes: [
        { id: 'f', langCode: 'en', headword: 'focus', depth: 0 },
        { id: 'a1', langCode: 'en', headword: 'a1', depth: -1 },
        { id: 'a2', langCode: 'en', headword: 'a2', depth: -2 },
        { id: 'a3', langCode: 'en', headword: 'a3', depth: -3 },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'a2', dstId: 'a1', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'a3', dstId: 'a2', relType: 'derived', sourceRef: 'r3' },
      ],
    };

    expect(layoutTree(wide).viewBox.width).toBeGreaterThan(
      layoutTree(narrow).viewBox.width,
    );
    expect(layoutTree(deep).viewBox.height).toBeGreaterThan(
      layoutTree(shallow).viewBox.height,
    );
  });
});
