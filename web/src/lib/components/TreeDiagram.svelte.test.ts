import { describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import TreeDiagram from './TreeDiagram.svelte';
import type { TreeSlice } from '../types';

const slice: TreeSlice = {
  focusId: 'f',
  nodes: [
    {
      id: 'f',
      langCode: 'en',
      headword: 'grandfather',
      isReconstructed: false,
      depth: 0,
    },
    {
      id: 'a1',
      langCode: 'en',
      headword: 'father',
      isReconstructed: false,
      depth: -1,
    },
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

  it('calls onnodeclick with the clicked node', async () => {
    const onnodeclick = vi.fn();
    const { getByText } = render(TreeDiagram, { slice, onnodeclick });

    await fireEvent.click(getByText('father (en)').closest('.node')!);

    expect(onnodeclick).toHaveBeenCalledOnce();
    expect(onnodeclick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'a1', headword: 'father' }),
    );
  });

  it('prefixes a reconstructed node headword with an asterisk', () => {
    const reconstructedSlice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: 'father',
          isReconstructed: false,
          depth: 0,
        },
        {
          id: 'a1',
          langCode: 'ine-pro',
          headword: 'peh₂-',
          isReconstructed: true,
          depth: -1,
        },
      ],
      edges: [{ srcId: 'a1', dstId: 'f', relType: 'root', sourceRef: 'ref1' }],
    };

    const { getByText } = render(TreeDiagram, {
      slice: reconstructedSlice,
      onnodeclick: vi.fn(),
    });

    expect(getByText('*peh₂- (ine-pro)')).toBeInTheDocument();
  });

  it('renders tree edges and cross-links with distinct classes', () => {
    const diamondSlice: TreeSlice = {
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
          isReconstructed: true,
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

    const { container } = render(TreeDiagram, {
      slice: diamondSlice,
      onnodeclick: vi.fn(),
    });

    expect(container.querySelectorAll('line.edge')).toHaveLength(3);
    expect(container.querySelectorAll('line.edge.cross-link')).toHaveLength(
      1,
    );
  });
});
