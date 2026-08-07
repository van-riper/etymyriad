import { describe, expect, it } from 'vitest';
import { layoutTree, NODE_HEIGHT } from './index';
import type { TreeNode, TreeSlice } from '../../shared/types';

function pathPoints(d: string): Array<[number, number]> {
  return d
    .split(/[ML] /)
    .filter(Boolean)
    .map((pair) => pair.trim().split(',').map(Number) as [number, number]);
}

describe('cross-link routing', () => {
  it('routes a same-row cross-link through the gap between rows', () => {
    const slice: TreeSlice = {
      focusId: 'gf',
      nodes: [
        {
          id: 'gf',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'father',
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'peh2',
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'father', dstId: 'gf', relType: 'affix', sourceRef: 'r1' },
        { srcId: 'peh2', dstId: 'gf', relType: 'root', sourceRef: 'r2' },
        { srcId: 'peh2', dstId: 'father', relType: 'root', sourceRef: 'r3' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    const crossLink = layout.edges.find((e) => e.kind === 'cross-link')!;
    const src = byId.get(crossLink.srcId)!;
    const dst = byId.get(crossLink.dstId)!;

    expect(crossLink.path).toBeDefined();
    const points = pathPoints(crossLink.path!);
    expect(points[0]).toEqual([src.x, src.y]);
    expect(points[points.length - 1]).toEqual([dst.x, dst.y]);

    // Same row (src.y === dst.y): the route must clear that row's
    // node boxes (half-height NODE_HEIGHT / 2) by a real margin,
    // not just barely.
    const [, laneStart, laneEnd] = points;
    expect(laneStart[1]).toEqual(laneEnd[1]);
    expect(Math.abs(laneStart[1] - src.y)).toBeGreaterThan(NODE_HEIGHT / 2);
  });

  it('shares a lane between same-row cross-links that do not overlap in x', () => {
    const slice: TreeSlice = {
      focusId: 'gf',
      nodes: [
        {
          id: 'gf',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'father',
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'peh2',
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'un1',
          langCode: 'en',
          headword: 'un1-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'un2',
          langCode: 'en',
          headword: 'un2-word',
          isReconstructed: false,
          depth: -1,
        },
      ],
      edges: [
        { srcId: 'father', dstId: 'gf', relType: 'affix', sourceRef: 'r1' },
        { srcId: 'peh2', dstId: 'gf', relType: 'root', sourceRef: 'r2' },
        { srcId: 'peh2', dstId: 'father', relType: 'root', sourceRef: 'r3' },
        { srcId: 'un1', dstId: 'gf', relType: 'root', sourceRef: 'r4' },
        { srcId: 'un2', dstId: 'gf', relType: 'affix', sourceRef: 'r5' },
        { srcId: 'un1', dstId: 'un2', relType: 'cognate', sourceRef: 'r6' },
      ],
    };

    // father/peh2 (leftmost pair) and un1/un2 (rightmost pair) never
    // span across each other, so routing them through the same lane
    // can never make their segments overlap.
    const layout = layoutTree(slice);
    const crossLinks = layout.edges.filter((e) => e.kind === 'cross-link');

    expect(crossLinks).toHaveLength(2);
    const laneYs = crossLinks.map((e) => pathPoints(e.path!)[1][1]);
    expect(laneYs[0]).toEqual(laneYs[1]);
    // Sharing a lane with nothing to cross means no bridge either.
    for (const edge of crossLinks) {
      expect(edge.path).not.toContain('A ');
    }
  });

  it('gives overlapping same-row cross-links separate lanes with a bridge', () => {
    const depth1 = (id: string, headword: string): TreeNode => ({
      id,
      langCode: 'en',
      headword,
      isReconstructed: false,
      depth: -1,
    });
    const slice: TreeSlice = {
      focusId: 'gf',
      nodes: [
        {
          id: 'gf',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
        depth1('aa', 'aa-word'),
        depth1('bb', 'bb-word'),
        depth1('cc', 'cc-word'),
        depth1('dd', 'dd-word'),
      ],
      edges: [
        { srcId: 'aa', dstId: 'gf', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'bb', dstId: 'gf', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'cc', dstId: 'gf', relType: 'derived', sourceRef: 'r3' },
        { srcId: 'dd', dstId: 'gf', relType: 'derived', sourceRef: 'r4' },
        // aa-cc spans over bb; bb-dd spans over cc -- their x-spans
        // genuinely overlap, so they can't share a lane.
        { srcId: 'aa', dstId: 'cc', relType: 'cognate', sourceRef: 'r5' },
        { srcId: 'bb', dstId: 'dd', relType: 'cognate', sourceRef: 'r6' },
      ],
    };

    const layout = layoutTree(slice);
    const byPair = new Map(
      layout.edges.map((e) => [`${e.srcId}:${e.dstId}`, e]),
    );
    const acEdge = byPair.get('aa:cc')!;
    const bdEdge = byPair.get('bb:dd')!;

    expect(acEdge.kind).toBe('cross-link');
    expect(bdEdge.kind).toBe('cross-link');

    const acLaneY = pathPoints(acEdge.path!)[1][1];
    const bdLaneY = pathPoints(bdEdge.path!)[1][1];
    expect(acLaneY).not.toEqual(bdLaneY);

    // aa-cc is the nearer (first-assigned) lane -- nothing crosses
    // it, so its path stays a plain bracket.
    expect(acEdge.path).not.toContain('A ');
    // bb-dd's own span [bb, dd] still crosses aa-cc's [aa, cc] at
    // bb -- its stem must bridge over aa-cc's horizontal run there.
    expect(bdEdge.path).toContain('A ');
  });

  // Handles M/L (one coordinate pair) and A (three: rx,ry then
  // x-rotation/large-arc/sweep flags then the endpoint) so a path
  // with bridges can still be inspected point by point.
  function parsePathCommands(
    d: string,
  ): Array<{ cmd: string; point: [number, number] }> {
    const tokens = d.trim().split(/\s+/);
    const commands: Array<{ cmd: string; point: [number, number] }> = [];
    let i = 0;
    while (i < tokens.length) {
      const cmd = tokens[i];
      if (cmd === 'M' || cmd === 'L') {
        const point = tokens[i + 1].split(',').map(Number) as [number, number];
        commands.push({ cmd, point });
        i += 2;
      } else if (cmd === 'A') {
        const point = tokens[i + 5].split(',').map(Number) as [number, number];
        commands.push({ cmd, point });
        i += 6;
      } else {
        i += 1;
      }
    }
    return commands;
  }

  it("dodges a stem sideways around a node's own single-child tree edge", () => {
    // b is an only child of gf, and has its own only child c --
    // b's outward tree edge to c sits at exactly b's x. a-b is an
    // unrelated cross-link (a and b are both direct, real children
    // of gf) landing on b, so its stem into b would otherwise run
    // collinear with b-c for the whole gap, not just cross it once.
    const slice: TreeSlice = {
      focusId: 'gf',
      nodes: [
        {
          id: 'gf',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a',
          langCode: 'en',
          headword: 'aa-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'b',
          langCode: 'en',
          headword: 'bb-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'c',
          langCode: 'en',
          headword: 'cc-word',
          isReconstructed: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 'a', dstId: 'gf', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'b', dstId: 'gf', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'c', dstId: 'b', relType: 'derived', sourceRef: 'r3' },
        { srcId: 'a', dstId: 'b', relType: 'cognate', sourceRef: 'r4' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    const b = byId.get('b')!;
    const c = byId.get('c')!;
    // b is c's only child's parent, so d3.tree() centers them:
    // exactly the single-child alignment that creates the conflict.
    expect(b.x).toEqual(c.x);

    const crossLink = layout.edges.find(
      (e) => e.srcId === 'a' && e.dstId === 'b',
    )!;
    expect(crossLink.kind).toBe('cross-link');

    const commands = parsePathCommands(crossLink.path!);
    const [last, secondToLast] = [...commands].reverse();

    // The path must still land exactly on b...
    expect(last.point).toEqual([b.x, b.y]);
    // ...but the run just before that isn't at b's x at all --
    // it's been shifted aside, not just bumped, since a plain bump
    // would leave it sitting back on b's x either side of the hop.
    expect(secondToLast.point[0]).not.toEqual(b.x);
    expect(secondToLast.point[1]).toEqual(b.y);
  });

  it("bridges a cross-link's horizontal run over an unrelated node's tree edge", () => {
    // d, e, f are siblings (all direct children of gf); e has its
    // own only child g, so e's outward tree edge sits at e's x. The
    // d-f cross-link's horizontal run spans past e's column even
    // though neither endpoint is e -- that's a single crossing, not
    // a collinear run, so this one gets a bridge, not a dodge.
    const slice: TreeSlice = {
      focusId: 'gf',
      nodes: [
        {
          id: 'gf',
          langCode: 'en',
          headword: 'grandfather',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'd',
          langCode: 'en',
          headword: 'dd-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'e',
          langCode: 'en',
          headword: 'ee-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'f',
          langCode: 'en',
          headword: 'ff-word',
          isReconstructed: false,
          depth: -1,
        },
        {
          id: 'g',
          langCode: 'en',
          headword: 'gg-word',
          isReconstructed: false,
          depth: -2,
        },
      ],
      edges: [
        { srcId: 'd', dstId: 'gf', relType: 'derived', sourceRef: 'r1' },
        { srcId: 'e', dstId: 'gf', relType: 'derived', sourceRef: 'r2' },
        { srcId: 'f', dstId: 'gf', relType: 'derived', sourceRef: 'r3' },
        { srcId: 'g', dstId: 'e', relType: 'derived', sourceRef: 'r4' },
        { srcId: 'd', dstId: 'f', relType: 'cognate', sourceRef: 'r5' },
      ],
    };

    const layout = layoutTree(slice);
    const byId = new Map(layout.nodes.map((n) => [n.id, n]));
    const d = byId.get('d')!;
    const e = byId.get('e')!;
    const f = byId.get('f')!;
    expect(d.x).toBeLessThan(e.x);
    expect(e.x).toBeLessThan(f.x);

    const crossLink = layout.edges.find(
      (e) => e.srcId === 'd' && e.dstId === 'f',
    )!;
    expect(crossLink.kind).toBe('cross-link');
    // Neither endpoint shares e's x, so this is a clean bridge, not
    // a dodge -- both ends should still land exactly on their node.
    const commands = parsePathCommands(crossLink.path!);
    expect(commands[0].point).toEqual([d.x, d.y]);
    expect(commands[commands.length - 1].point).toEqual([f.x, f.y]);
    expect(crossLink.path).toContain('A ');
  });
});
