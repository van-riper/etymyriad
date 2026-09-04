import { describe, expect, it } from 'vitest';
import { layoutTree } from './index';
import type { TreeSlice } from '../../shared/types';

describe('sibling ordering', () => {
  it('orders same-generation siblings alphabetically by headword', () => {
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
          id: 'z',
          langCode: 'en',
          headword: 'zeta',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'a',
          langCode: 'en',
          headword: 'alpha',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'm',
          langCode: 'en',
          headword: 'mid',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
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

  it('orders composed siblings by piece position, not headword', () => {
    // "happy" sorts before "un-" alphabetically, but "un-" is piece 1
    // (the prefix) and "happy" is piece 2 (the root) of "unhappy" --
    // composition order must win over the alphabetical fallback.
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'unhappy',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 'happy',
          langCode: 'en',
          headword: 'happy',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'un',
          langCode: 'en',
          headword: 'un-',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        {
          srcId: 'un',
          dstId: 'f',
          relType: 'affix',
          sourceRef: 'r1',
          pieceOrder: 1,
        },
        {
          srcId: 'happy',
          dstId: 'f',
          relType: 'affix',
          sourceRef: 'r2',
          pieceOrder: 2,
        },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get('un')!.x).toBeLessThan(byId.get('happy')!.x);
  });

  it('keeps piece order even alongside a non-piece sibling', () => {
    // Real "needler" bug: "needle" (piece 1) and "-er" (piece 2) are
    // the affix decomposition, but "nedlere" (an inherited Middle
    // English ancestor, no piece order) is a third sibling whose
    // headword alphabetically falls between the other two. Comparing
    // a piece to a non-piece by headword alone isn't transitive:
    // "-er" < "nedlere" < "needle" alphabetically contradicts "needle"
    // (piece 1) sorting before "-er" (piece 2). This only holds
    // if pieces are grouped ahead of non-pieces rather than
    // interleaved by headword.
    const slice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'needler',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        // Sibling order here (before sort) is what makes the old,
        // non-transitive comparator actually misorder needle/-er --
        // a different input order happened not to trigger it.
        {
          id: 'needle',
          langCode: 'en',
          headword: 'needle',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'nedlere',
          langCode: 'enm',
          headword: 'nedlere',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'er',
          langCode: 'en',
          headword: '-er',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        {
          srcId: 'needle',
          dstId: 'f',
          relType: 'affix',
          sourceRef: 'r1',
          pieceOrder: 1,
        },
        {
          srcId: 'nedlere',
          dstId: 'f',
          relType: 'inherited',
          sourceRef: 'r3',
        },
        {
          srcId: 'er',
          dstId: 'f',
          relType: 'affix',
          sourceRef: 'r2',
          pieceOrder: 2,
        },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get('needle')!.x).toBeLessThan(byId.get('er')!.x);
  });
});

describe('variable-width spacing', () => {
  it('keeps variable-width siblings from overlapping', () => {
    const longHeadword = 'a'.repeat(40);
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
          id: 'short',
          langCode: 'en',
          headword: 'a',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'long',
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'short', dstId: 'f', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'long', dstId: 'f', relType: 'derived', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    const a = byId.get('short')!;
    const b = byId.get('long')!;

    expect(Math.abs(a.x - b.x)).toBeGreaterThanOrEqual((a.width + b.width) / 2);
  });

  it('keeps variable-width cousins from overlapping', () => {
    const longHeadword = 'a'.repeat(40);
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
          id: 'pA',
          langCode: 'en',
          headword: 'pa',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'pB',
          langCode: 'en',
          headword: 'pb',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'gcA',
          langCode: 'en',
          headword: 'a',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
        {
          id: 'gcB',
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 'pA', dstId: 'f', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'pB', dstId: 'f', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'gcA', dstId: 'pA', relType: 'derived', sourceRef: 'r3' },
        { srcId: 'gcB', dstId: 'pB', relType: 'derived', sourceRef: 'r4' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    const a = byId.get('gcA')!;
    const b = byId.get('gcB')!;

    expect(Math.abs(a.x - b.x)).toBeGreaterThanOrEqual((a.width + b.width) / 2);
  });

  it('keeps cousins spaced twice as far apart as plain siblings, at floor width', () => {
    const siblingSlice: TreeSlice = {
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
          id: 's1',
          langCode: 'en',
          headword: 's1',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 's2',
          langCode: 'en',
          headword: 's2',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 's1', dstId: 'f', relType: 'derived', sourceRef: 'r1' },
        { srcId: 's2', dstId: 'f', relType: 'derived', sourceRef: 'r2' },
      ],
    };
    const cousinSlice: TreeSlice = {
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
          id: 'pA',
          langCode: 'en',
          headword: 'pa',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'pB',
          langCode: 'en',
          headword: 'pb',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 'cA',
          langCode: 'en',
          headword: 'ca',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
        {
          id: 'cB',
          langCode: 'en',
          headword: 'cb',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 'pA', dstId: 'f', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'pB', dstId: 'f', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'cA', dstId: 'pA', relType: 'derived', sourceRef: 'r3' },
        { srcId: 'cB', dstId: 'pB', relType: 'derived', sourceRef: 'r4' },
      ],
    };

    const siblingLayout = layoutTree(siblingSlice);
    const siblingById = new Map(siblingLayout.nodes.map((n) => [n.id, n]));
    const siblingGap = Math.abs(
      siblingById.get('s1')!.x - siblingById.get('s2')!.x,
    );

    const cousinLayout = layoutTree(cousinSlice);
    const cousinById = new Map(cousinLayout.nodes.map((n) => [n.id, n]));
    const cousinGap = Math.abs(
      cousinById.get('cA')!.x - cousinById.get('cB')!.x,
    );

    expect(cousinGap).toBeCloseTo(2 * siblingGap);
  });
});
