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
});
