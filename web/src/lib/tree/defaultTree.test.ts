import { describe, expect, it } from 'vitest';
import {
  DEFAULT_HEADWORD,
  DEFAULT_LANG,
  DEFAULT_TREE_SLICE,
} from './defaultTree';

describe('DEFAULT_TREE_SLICE', () => {
  it('has a focus node matching the default lang/headword', () => {
    const focus = DEFAULT_TREE_SLICE.nodes.find(
      (n) => n.id === DEFAULT_TREE_SLICE.focusId,
    );

    expect(focus).toBeDefined();
    expect(focus?.langCode).toBe(DEFAULT_LANG);
    expect(focus?.headword).toBe(DEFAULT_HEADWORD);
    expect(focus?.depth).toBe(0);
  });

  it('has every edge referencing a node present in the slice', () => {
    const nodeIds = new Set(DEFAULT_TREE_SLICE.nodes.map((n) => n.id));

    for (const edge of DEFAULT_TREE_SLICE.edges) {
      expect(nodeIds.has(edge.srcId)).toBe(true);
      expect(nodeIds.has(edge.dstId)).toBe(true);
    }
  });
});
