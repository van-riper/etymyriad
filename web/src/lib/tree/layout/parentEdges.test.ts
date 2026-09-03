import { describe, expect, it } from 'vitest';
import { layoutTree } from './index';
import { primaryRelType } from './parentEdges';
import type { TreeSlice } from '../../shared/types';

describe('primaryRelType', () => {
  it('picks the highest-lineage-priority relType among duplicates', () => {
    expect(primaryRelType(['cognate', 'inherited', 'derived'])).toBe(
      'inherited',
    );
  });

  it('returns the only relType when there is no duplicate', () => {
    expect(primaryRelType(['affix'])).toBe('affix');
  });

  it('treats inflection as real lineage, between derived and calque', () => {
    expect(primaryRelType(['inflection', 'calque'])).toBe('inflection');
    expect(primaryRelType(['derived', 'inflection'])).toBe('derived');
  });
});

describe('parent-edge picking', () => {
  it('breaks a same-depth parent tie by rel_type priority, preferring lineage over morphology', () => {
    const slice: TreeSlice = {
      focusId: 'focus',
      nodes: [
        {
          id: 'focus',
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 'A',
          langCode: 'en',
          headword: 'a-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'B',
          langCode: 'en',
          headword: 'b-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'C',
          langCode: 'en',
          headword: 'c-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 'A', dstId: 'focus', relType: 'derived', sourceRef: 'rA' },
        { srcId: 'B', dstId: 'focus', relType: 'derived', sourceRef: 'rB' },
        { srcId: 'C', dstId: 'A', relType: 'affix', sourceRef: 'rCA' },
        { srcId: 'C', dstId: 'B', relType: 'inherited', sourceRef: 'rCB' },
      ],
    };

    const layout = layoutTree(slice);
    const edgeCA = layout.edges.find((e) => e.srcId === 'C' && e.dstId === 'A');
    const edgeCB = layout.edges.find((e) => e.srcId === 'C' && e.dstId === 'B');

    expect(edgeCB).toBeDefined();
    expect(edgeCA).toBeUndefined();
  });

  it('collapses duplicate edges between the same node pair into one line', () => {
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 'a1',
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'a1', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'a1', dstId: 'f', relType: 'root', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);

    expect(layout.edges).toHaveLength(1);
    expect(layout.edges[0].relTypes.sort()).toEqual(['inherited', 'root']);
    expect(layout.edges[0].sourceRefs.sort()).toEqual(['r1', 'r2']);
  });

  it("drops the real grandfather/father/peh₂- diamond's extra edge", () => {
    // grandfather has a direct affix edge to father and a direct root
    // edge to peh₂-; father also has a direct root edge to that same
    // peh₂-. treeSlice already resolved peh₂- to its shortest depth
    // (-1, direct), so both father and peh₂- land at depth -1 here --
    // the peh₂--father edge connects two same-depth nodes and can be
    // neither's placing edge.
    const slice: TreeSlice = {
      focusId: 'gf',
      nodes: [
        {
          id: 'gf',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 'father',
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'peh2',
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
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

    const byPair = new Map(
      layout.edges.map((e) => [`${e.srcId}:${e.dstId}`, e]),
    );
    expect([...byPair.keys()].sort()).toEqual(['father:gf', 'peh2:gf']);
  });

  it('re-homes a lineage ancestor through a nearer ancestor instead of its own tied shortcut to focus', () => {
    // mega- (en) has three direct ancestors, all lineage edges:
    // μέγᾰς, μέγας, and meǵh₂s (ine-pro). meǵh₂s is also μέγας's own
    // direct ancestor (inherited), so treeSlice's BFS gives meǵh₂s the
    // same depth (-1) as μέγας via its own direct 'derived' edge to
    // mega- -- a real ETYM-179 repro (Wiktionary cites both the
    // immediate and the deeper root). meǵh₂s should chain through
    // μέγας (its nearer lineage ancestor) rather than render as a
    // third tied sibling, so the direct meǵh₂s->mega- edge is dropped
    // rather than becoming meǵh₂s's placing edge.
    const slice: TreeSlice = {
      focusId: 'mega',
      nodes: [
        {
          id: 'mega',
          langCode: 'en',
          headword: 'mega-',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 'megas1',
          langCode: 'grc',
          headword: 'μέγᾰς',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'megas2',
          langCode: 'grc',
          headword: 'μέγας',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'meghs',
          langCode: 'ine-pro',
          headword: 'meǵh₂s',
          isReconstructed: true,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'megas1', dstId: 'mega', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'megas2', dstId: 'mega', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'meghs', dstId: 'mega', relType: 'derived', sourceRef: 'r3' },
        {
          srcId: 'meghs',
          dstId: 'megas2',
          relType: 'inherited',
          sourceRef: 'r4',
        },
      ],
    };

    const layout = layoutTree(slice);
    const byPair = new Map(
      layout.edges.map((e) => [`${e.srcId}:${e.dstId}`, e]),
    );

    expect([...byPair.keys()].sort()).toEqual([
      'megas1:mega',
      'megas2:mega',
      'meghs:megas2',
    ]);

    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    // meghs now sits one row farther out than megas2, its new parent,
    // rather than tied with it at the same depth-1 row.
    expect(Math.abs(byId.get('meghs')!.y)).toBeGreaterThan(
      Math.abs(byId.get('megas2')!.y),
    );
  });

  it('falls back to the focus as parent when a node has no edge reaching its resolved depth', () => {
    // x sits at depth -1 but its only edges are a cyclic pair with
    // a, another depth -1 node -- neither edge reaches depth 0, so
    // pickParentEdges finds no valid candidate for x and must fall
    // back to the focus rather than crashing.
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 'a',
          langCode: 'en',
          headword: 'a-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'x',
          langCode: 'en',
          headword: 'x-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'a', dstId: 'f', relType: 'inherited', sourceRef: 'r1' },
        { srcId: 'x', dstId: 'a', relType: 'cognate', sourceRef: 'r2' },
        { srcId: 'a', dstId: 'x', relType: 'cognate', sourceRef: 'r3' },
      ],
    };

    expect(() => layoutTree(slice)).not.toThrow();

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get('x')).toBeDefined();
    // Falling back to the focus makes x a direct child of f, at the
    // same tree row as a (also a direct child of f).
    expect(byId.get('x')!.y).toBe(byId.get('a')!.y);
  });
});
