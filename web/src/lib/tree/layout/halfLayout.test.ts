import { describe, expect, it } from 'vitest';
import { layoutTree, NODE_HEIGHT } from './index';
import type { TreeSlice } from '../../shared/types';

describe('sibling ordering', () => {
  it('orders same-generation siblings alphabetically by headword', () => {
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
          headword: 'zeta',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 3,
          langCode: 'en',
          headword: 'alpha',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 4,
          langCode: 'en',
          headword: 'mid',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 2, dstId: 1, relType: 'derived', sourceRef: 'r1' },
        { srcId: 3, dstId: 1, relType: 'derived', sourceRef: 'r2' },
        { srcId: 4, dstId: 1, relType: 'derived', sourceRef: 'r3' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get(3)!.y).toBeLessThan(byId.get(4)!.y);
    expect(byId.get(4)!.y).toBeLessThan(byId.get(2)!.y);
  });

  it('orders composed siblings by piece position, not headword', () => {
    // "happy" sorts before "un-" alphabetically, but "un-" is piece 1
    // (the prefix) and "happy" is piece 2 (the root) of "unhappy" --
    // composition order must win over the alphabetical fallback.
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'en',
          headword: 'unhappy',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 5,
          langCode: 'en',
          headword: 'happy',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 6,
          langCode: 'en',
          headword: 'un-',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        {
          srcId: 6,
          dstId: 1,
          relType: 'affix',
          sourceRef: 'r1',
          pieceOrder: 1,
        },
        {
          srcId: 5,
          dstId: 1,
          relType: 'affix',
          sourceRef: 'r2',
          pieceOrder: 2,
        },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get(6)!.y).toBeLessThan(byId.get(5)!.y);
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
      focusId: 1,
      nodes: [
        {
          id: 1,
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
          id: 7,
          langCode: 'en',
          headword: 'needle',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 8,
          langCode: 'enm',
          headword: 'nedlere',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 9,
          langCode: 'en',
          headword: '-er',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        {
          srcId: 7,
          dstId: 1,
          relType: 'affix',
          sourceRef: 'r1',
          pieceOrder: 1,
        },
        {
          srcId: 8,
          dstId: 1,
          relType: 'inherited',
          sourceRef: 'r3',
        },
        {
          srcId: 9,
          dstId: 1,
          relType: 'affix',
          sourceRef: 'r2',
          pieceOrder: 2,
        },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get(7)!.y).toBeLessThan(byId.get(9)!.y);
  });

  it('sorts a single-piece suffix after its non-piece siblings', () => {
    // Real "spezifisch" (de) bug: "-isch" is the only argument in its
    // own {{af|de|-isch}} call, so it gets piece_order 1 simply for
    // being the lone slot -- not because it's positionally first in
    // the word. Its base ("spécifique"/"specificus") is asserted via
    // separate, non-piece bor/der edges instead. A leading dash is
    // Wiktionary's own convention for "this is a suffix", so it must
    // sort after its non-piece siblings, not before.
    const slice: TreeSlice = {
      focusId: 1,
      nodes: [
        {
          id: 1,
          langCode: 'de',
          headword: 'spezifisch',
          isReconstructed: false,
          isRedlink: false,
          depth: 0,
        },
        {
          id: 10,
          langCode: 'fr',
          headword: 'spécifique',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 11,
          langCode: 'de',
          headword: '-isch',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 12,
          langCode: 'la-lat',
          headword: 'specificus',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 10, dstId: 1, relType: 'borrowed', sourceRef: 'r1' },
        {
          srcId: 11,
          dstId: 1,
          relType: 'affix',
          sourceRef: 'r2',
          pieceOrder: 1,
        },
        { srcId: 12, dstId: 1, relType: 'derived', sourceRef: 'r3' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));

    expect(byId.get(10)!.y).toBeLessThan(byId.get(11)!.y);
    expect(byId.get(12)!.y).toBeLessThan(byId.get(11)!.y);
  });
});

describe('variable-width spacing', () => {
  it('keeps variable-width siblings from overlapping', () => {
    const longHeadword = 'a'.repeat(40);
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
          id: 13,
          langCode: 'en',
          headword: 'a',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 14,
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 13, dstId: 1, relType: 'derived', sourceRef: 'r1' },
        { srcId: 14, dstId: 1, relType: 'derived', sourceRef: 'r2' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    const a = byId.get(13)!;
    const b = byId.get(14)!;

    expect(Math.abs(a.y - b.y)).toBeGreaterThanOrEqual(NODE_HEIGHT);
  });

  it('keeps variable-width cousins from overlapping', () => {
    const longHeadword = 'a'.repeat(40);
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
          id: 15,
          langCode: 'en',
          headword: 'pa',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 16,
          langCode: 'en',
          headword: 'pb',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 17,
          langCode: 'en',
          headword: 'a',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
        {
          id: 18,
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 15, dstId: 1, relType: 'derived', sourceRef: 'r1' },
        { srcId: 16, dstId: 1, relType: 'derived', sourceRef: 'r2' },
        { srcId: 17, dstId: 15, relType: 'derived', sourceRef: 'r3' },
        { srcId: 18, dstId: 16, relType: 'derived', sourceRef: 'r4' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    const a = byId.get(17)!;
    const b = byId.get(18)!;

    expect(Math.abs(a.y - b.y)).toBeGreaterThanOrEqual(NODE_HEIGHT);
  });

  it('keeps cousins spaced twice as far apart as plain siblings, at floor width', () => {
    const siblingSlice: TreeSlice = {
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
          id: 19,
          langCode: 'en',
          headword: 's1',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 20,
          langCode: 'en',
          headword: 's2',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 19, dstId: 1, relType: 'derived', sourceRef: 'r1' },
        { srcId: 20, dstId: 1, relType: 'derived', sourceRef: 'r2' },
      ],
    };
    const cousinSlice: TreeSlice = {
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
          id: 15,
          langCode: 'en',
          headword: 'pa',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 16,
          langCode: 'en',
          headword: 'pb',
          isReconstructed: false,
          isRedlink: false,
          depth: -1,
        },
        {
          id: 21,
          langCode: 'en',
          headword: 'ca',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
        {
          id: 22,
          langCode: 'en',
          headword: 'cb',
          isReconstructed: false,
          isRedlink: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 15, dstId: 1, relType: 'derived', sourceRef: 'r1' },
        { srcId: 16, dstId: 1, relType: 'derived', sourceRef: 'r2' },
        { srcId: 21, dstId: 15, relType: 'derived', sourceRef: 'r3' },
        { srcId: 22, dstId: 16, relType: 'derived', sourceRef: 'r4' },
      ],
    };

    const siblingLayout = layoutTree(siblingSlice);
    const siblingById = new Map(siblingLayout.nodes.map((n) => [n.id, n]));
    const siblingGap = Math.abs(
      siblingById.get(19)!.y - siblingById.get(20)!.y,
    );

    const cousinLayout = layoutTree(cousinSlice);
    const cousinById = new Map(cousinLayout.nodes.map((n) => [n.id, n]));
    const cousinGap = Math.abs(cousinById.get(21)!.y - cousinById.get(22)!.y);

    expect(cousinGap).toBeCloseTo(2 * siblingGap);
  });
});
