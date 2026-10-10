import { describe, expect, it } from 'vitest';
import { layoutTree } from './index';
import { primaryRelType } from './parentEdges';
import type { TreeSlice } from '../../shared/types';

describe('primaryRelType', () => {
  it('picks the highest-lineage-priority relType among duplicates', () => {
    expect(primaryRelType(['mention', 'inherited', 'derived'])).toBe(
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
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 2,
          langCode: 'en',
          headword: 'a-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 3,
          langCode: 'en',
          headword: 'b-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 4,
          langCode: 'en',
          headword: 'c-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 2, dstId: 1, relType: 'derived', sourceRef: 'rA' },
        { srcId: 3, dstId: 1, relType: 'derived', sourceRef: 'rB' },
        { srcId: 4, dstId: 2, relType: 'affix', sourceRef: 'rCA' },
        { srcId: 4, dstId: 3, relType: 'inherited', sourceRef: 'rCB' },
      ],
    };

    const layout = layoutTree(slice);
    const edgeCA = layout.edges.find((e) => e.srcId === 4 && e.dstId === 2);
    const edgeCB = layout.edges.find((e) => e.srcId === 4 && e.dstId === 3);

    expect(edgeCB).toBeDefined();
    expect(edgeCA).toBeUndefined();
  });

  it('collapses duplicate edges between the same node pair into one line', () => {
    const slice: TreeSlice = {
      focusId: 5,
      nodes: [
        {
          id: 5,
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 6,
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 6, dstId: 5, relType: 'inherited', sourceRef: 'r1' },
        { srcId: 6, dstId: 5, relType: 'root', sourceRef: 'r2' },
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
      focusId: 7,
      nodes: [
        {
          id: 7,
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 8,
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 9,
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 8, dstId: 7, relType: 'affix', sourceRef: 'r1' },
        { srcId: 9, dstId: 7, relType: 'root', sourceRef: 'r2' },
        {
          srcId: 9,
          dstId: 8,
          relType: 'root',
          sourceRef: 'r3',
        },
      ],
    };

    const layout = layoutTree(slice);

    const byPair = new Map(
      layout.edges.map((e) => [`${e.srcId}:${e.dstId}`, e]),
    );
    expect([...byPair.keys()].sort()).toEqual(['8:7', '9:7']);
  });

  it('re-homes a lineage ancestor through a nearer ancestor instead of its own tied shortcut to focus', () => {
    // mega- (en) has three direct ancestors, all lineage edges:
    // μέγᾰς, μέγας, and meǵh₂s (ine-pro). meǵh₂s is also μέγας's own
    // direct ancestor (inherited), so treeSlice's BFS gives meǵh₂s the
    // same depth (-1) as μέγας via its own direct 'derived' edge to
    // mega-: Wiktionary cites both the immediate and the deeper
    // root. meǵh₂s should chain through
    // μέγας (its nearer lineage ancestor) rather than render as a
    // third tied sibling, so the direct meǵh₂s->mega- edge is dropped
    // rather than becoming meǵh₂s's placing edge.
    const slice: TreeSlice = {
      focusId: 10,
      nodes: [
        {
          id: 10,
          langCode: 'en',
          headword: 'mega-',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 11,
          langCode: 'grc',
          headword: 'μέγᾰς',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 12,
          langCode: 'grc',
          headword: 'μέγας',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 13,
          langCode: 'ine-pro',
          headword: 'meǵh₂s',
          isReconstructed: true,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 11, dstId: 10, relType: 'derived', sourceRef: 'r1' },
        { srcId: 12, dstId: 10, relType: 'derived', sourceRef: 'r2' },
        { srcId: 13, dstId: 10, relType: 'derived', sourceRef: 'r3' },
        {
          srcId: 13,
          dstId: 12,
          relType: 'inherited',
          sourceRef: 'r4',
        },
      ],
    };

    const layout = layoutTree(slice);
    const byPair = new Map(
      layout.edges.map((e) => [`${e.srcId}:${e.dstId}`, e]),
    );

    expect([...byPair.keys()].sort()).toEqual(['11:10', '12:10', '13:12']);

    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    // meghs now sits one row farther out than megas2, its new parent,
    // rather than tied with it at the same depth-1 row.
    expect(Math.abs(byId.get(13)!.y)).toBeGreaterThan(
      Math.abs(byId.get(12)!.y),
    );
  });

  it('prefers the correctly-directed direct edge over a higher-ranked inverted one', () => {
    // la:adamas sits at depth -3, but its own ancestor grc:ἀδάμας also
    // reaches en:adamantium two hops away by a separate path
    // (omitted here), landing grc:ἀδάμας at depth -2 -- the same
    // resolved depth as la:adamas's real descendant, la:adamantem.
    // An unguarded `direct` bucket picks the inverted edge to
    // grc:ἀδάμας since 'derived' outranks 'inflection', dropping
    // adamas->adamantem and leaving adamantem parentless.
    const slice: TreeSlice = {
      focusId: 14,
      nodes: [
        {
          id: 14,
          langCode: 'en',
          headword: 'adamantium',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 15,
          langCode: 'la',
          headword: 'adamantem',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
        {
          id: 16,
          langCode: 'la',
          headword: 'adamas',
          isReconstructed: false,
          isRedlink: false,
          depth: -3,
        },
        {
          id: 17,
          langCode: 'grc',
          headword: 'ἀδάμας',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
      ],
      edges: [
        {
          srcId: 15,
          dstId: 14,
          relType: 'inherited',
          sourceRef: 'r0',
        },
        {
          srcId: 16,
          dstId: 15,
          relType: 'inflection',
          sourceRef: 'r1',
        },
        {
          srcId: 17,
          dstId: 16,
          relType: 'derived',
          sourceRef: 'r2',
        },
      ],
    };

    const layout = layoutTree(slice);
    const byPair = new Map(
      layout.edges.map((e) => [`${e.srcId}:${e.dstId}`, e]),
    );

    expect(byPair.has('16:15')).toBe(true);
    expect(byPair.has('17:16')).toBe(false);
  });

  it('falls back to the focus as parent when a node has no edge reaching its resolved depth', () => {
    // x sits at depth -1 but its only edges are a cyclic pair with
    // a, another depth -1 node: neither edge reaches depth 0, so
    // pickParentEdges finds no valid candidate for x and must fall
    // back to the focus rather than crashing.
    const slice: TreeSlice = {
      focusId: 5,
      nodes: [
        {
          id: 5,
          langCode: 'en',
          headword: 'focus',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 18,
          langCode: 'en',
          headword: 'a-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 19,
          langCode: 'en',
          headword: 'x-word',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 18, dstId: 5, relType: 'inherited', sourceRef: 'r1' },
        { srcId: 19, dstId: 18, relType: 'mention', sourceRef: 'r2' },
        { srcId: 18, dstId: 19, relType: 'mention', sourceRef: 'r3' },
      ],
    };

    expect(() => layoutTree(slice)).not.toThrow();

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get(19)).toBeDefined();
    // Falling back to the focus makes x a direct child of f, at the
    // same tree row as a (also a direct child of f).
    expect(byId.get(19)!.y).toBe(byId.get(18)!.y);
  });
});
