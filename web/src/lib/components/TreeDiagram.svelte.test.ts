import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import { tick } from 'svelte';
import TreeDiagram from './TreeDiagram.svelte';
import { layoutTree } from '../utils/treeLayout';
import { computeFitTransform, FLOOR_SCALE } from '../utils/zoomFit';
import type { TreeNode, TreeSlice } from '../types';

function mockContainerSize(width: number, height: number) {
  Object.defineProperty(SVGSVGElement.prototype, 'clientWidth', {
    configurable: true,
    value: width,
  });
  Object.defineProperty(SVGSVGElement.prototype, 'clientHeight', {
    configurable: true,
    value: height,
  });
}

// fireEvent's MouseEvent construction rejects a `view` init that
// doesn't pass jsdom's internal isWindow() brand check under Vitest's
// jsdom environment (a known environment quirk, unrelated to this
// component) -- d3-drag's pan handling needs a real `view` to read
// `view.document`, so it's patched on post-construction instead of
// passed through the constructor.
function dispatchMouseEvent(
  target: EventTarget,
  type: string,
  init: MouseEventInit,
) {
  const event = new MouseEvent(type, init);
  Object.defineProperty(event, 'view', { value: window, configurable: true });
  target.dispatchEvent(event);
}

function zoomLayerTransform(container: HTMLElement): {
  x: number;
  y: number;
  k: number;
} {
  const attr = container
    .querySelector('g.zoom-layer')!
    .getAttribute('transform')!;
  const match = attr.match(/translate\(([^,]+),([^)]+)\) scale\(([^)]+)\)/)!;
  return { x: Number(match[1]), y: Number(match[2]), k: Number(match[3]) };
}

function linearChainSlice(length: number): TreeSlice {
  const nodes: TreeNode[] = [
    {
      id: 'f',
      langCode: 'en',
      headword: 'f',
      isReconstructed: false,
      depth: 0,
    },
  ];
  const edges: TreeSlice['edges'] = [];
  for (let i = 1; i <= length; i++) {
    nodes.push({
      id: `a${i}`,
      langCode: 'en',
      headword: `a${i}`,
      isReconstructed: false,
      depth: -i,
    });
    edges.push({
      srcId: `a${i}`,
      dstId: i === 1 ? 'f' : `a${i - 1}`,
      relType: 'derived',
      sourceRef: `ref${i}`,
    });
  }
  return { focusId: 'f', nodes, edges };
}

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
  afterEach(() => {
    delete (SVGSVGElement.prototype as unknown as Record<string, unknown>)
      .clientWidth;
    delete (SVGSVGElement.prototype as unknown as Record<string, unknown>)
      .clientHeight;
  });

  it('auto-fits a small tree to the container on load, as before', async () => {
    mockContainerSize(800, 600);
    const { container } = render(TreeDiagram, { slice, onnodeclick: vi.fn() });
    await tick();

    const expected = computeFitTransform(layoutTree(slice).viewBox, 800, 600);
    const actual = zoomLayerTransform(container);

    expect(actual.k).toBeCloseTo(expected.k);
    expect(actual.x).toBeCloseTo(expected.x);
    expect(actual.y).toBeCloseTo(expected.y);
  });

  it('never renders a tree of 100+ nodes below the floor scale on load', async () => {
    mockContainerSize(800, 600);
    const bigSlice = linearChainSlice(120);
    const { container } = render(TreeDiagram, {
      slice: bigSlice,
      onnodeclick: vi.fn(),
    });
    await tick();

    expect(zoomLayerTransform(container).k).toBeCloseTo(FLOOR_SCALE);
  });

  it('zooms in on the cursor when the wheel scrolls up', async () => {
    mockContainerSize(800, 600);
    const { container } = render(TreeDiagram, { slice, onnodeclick: vi.fn() });
    await tick();
    const before = zoomLayerTransform(container).k;

    await fireEvent.wheel(container.querySelector('svg')!, {
      deltaY: -100,
      clientX: 400,
      clientY: 300,
    });
    await tick();

    expect(zoomLayerTransform(container).k).toBeGreaterThan(before);
  });

  it('pans the tree when dragged', async () => {
    mockContainerSize(800, 600);
    const { container } = render(TreeDiagram, { slice, onnodeclick: vi.fn() });
    await tick();
    const before = zoomLayerTransform(container);

    const svg = container.querySelector('svg')!;
    dispatchMouseEvent(svg, 'mousedown', { clientX: 100, clientY: 100 });
    dispatchMouseEvent(window, 'mousemove', { clientX: 160, clientY: 100 });
    dispatchMouseEvent(window, 'mouseup', { clientX: 160, clientY: 100 });
    await tick();
    // d3-drag suppresses the click that follows a real drag via a
    // one-shot window-level listener removed on a 0ms timeout -- wait
    // for it so it doesn't eat a later test's click.
    await new Promise((resolve) => setTimeout(resolve, 0));

    const after = zoomLayerTransform(container);
    expect(after.x - before.x).toBeCloseTo(60);
    expect(after.y).toBeCloseTo(before.y);
  });

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
    expect(container.querySelectorAll('line.edge.cross-link')).toHaveLength(1);
  });
});
