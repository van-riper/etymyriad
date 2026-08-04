import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/svelte';
import TreeDiagram from './TreeDiagram.svelte';
import type { TreeSlice } from '../types';

const slice: TreeSlice = {
  focusId: 'f',
  nodes: [
    { id: 'f', langCode: 'en', headword: 'grandfather', depth: 0 },
    { id: 'a1', langCode: 'en', headword: 'father', depth: -1 },
  ],
  edges: [{ srcId: 'a1', dstId: 'f', relType: 'affix', sourceRef: 'ref1' }],
};

describe('TreeDiagram', () => {
  it('renders one node per slice entry with headword and lang code', () => {
    const { getByText } = render(TreeDiagram, {
      slice,
      onnodeclick: vi.fn(),
    });

    expect(getByText('grandfather (en)')).toBeInTheDocument();
    expect(getByText('father (en)')).toBeInTheDocument();
  });

  it('marks the focus node distinctly from other nodes', () => {
    const { getByText } = render(TreeDiagram, {
      slice,
      onnodeclick: vi.fn(),
    });

    const focusNode = getByText('grandfather (en)').closest('.node');
    const otherNode = getByText('father (en)').closest('.node');

    expect(focusNode).toHaveClass('focus');
    expect(otherNode).not.toHaveClass('focus');
  });
});
