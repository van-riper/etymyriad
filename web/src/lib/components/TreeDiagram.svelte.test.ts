import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import { tick } from 'svelte';
import { toast } from 'svelte-sonner';
import TreeDiagram from './TreeDiagram.svelte';
import { layoutTree, MAX_SIBLINGS_PER_PARENT } from '../utils/treeLayout';
import { computeFitTransform, FLOOR_SCALE } from '../utils/zoomFit';
import type { TreeNode, TreeSlice } from '../types';

vi.mock('svelte-sonner', () => ({
  toast: {
    info: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}));

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

function wideFanoutSlice(): TreeSlice {
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
  const childCount = MAX_SIBLINGS_PER_PARENT + 5;
  for (let i = 0; i < childCount; i++) {
    const id = `c${String(i).padStart(2, '0')}`;
    nodes.push({
      id,
      langCode: 'en',
      headword: id,
      isReconstructed: false,
      depth: 1,
    });
    edges.push({ srcId: 'f', dstId: id, relType: 'derived', sourceRef: id });
  }
  return { focusId: 'f', nodes, edges };
}

function baseHandlers() {
  return { onnodeclick: vi.fn(), onnodedblclick: vi.fn() };
}

describe('TreeDiagram', () => {
  afterEach(() => {
    delete (SVGSVGElement.prototype as unknown as Record<string, unknown>)
      .clientWidth;
    delete (SVGSVGElement.prototype as unknown as Record<string, unknown>)
      .clientHeight;
    vi.clearAllMocks();
  });

  it('toasts once when the initial fit is clamped to the floor scale', async () => {
    mockContainerSize(800, 600);
    render(TreeDiagram, { slice: linearChainSlice(120), ...baseHandlers() });
    await tick();

    expect(toast.info).toHaveBeenCalledOnce();
  });

  it('does not toast when the initial fit is not clamped', async () => {
    mockContainerSize(800, 600);
    render(TreeDiagram, { slice, ...baseHandlers() });
    await tick();

    expect(toast.info).not.toHaveBeenCalled();
  });

  it('auto-fits a small tree to the container on load, as before', async () => {
    mockContainerSize(800, 600);
    const { container } = render(TreeDiagram, { slice, ...baseHandlers() });
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
      ...baseHandlers(),
    });
    await tick();

    expect(zoomLayerTransform(container).k).toBeCloseTo(FLOOR_SCALE);
  });

  it('zooms in on the cursor when the wheel scrolls up', async () => {
    mockContainerSize(800, 600);
    const { container } = render(TreeDiagram, { slice, ...baseHandlers() });
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
    const { container } = render(TreeDiagram, { slice, ...baseHandlers() });
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
      ...baseHandlers(),
    });

    expect(getByText('grandfather (en)')).toBeInTheDocument();
    expect(getByText('father (en)')).toBeInTheDocument();
  });

  it('marks the focus node distinctly from other nodes', () => {
    const { getByText } = render(TreeDiagram, {
      slice,
      ...baseHandlers(),
    });

    const focusNode = getByText('grandfather (en)').closest('.node');
    const otherNode = getByText('father (en)').closest('.node');

    expect(focusNode).toHaveClass('focus');
    expect(otherNode).not.toHaveClass('focus');
  });

  it('calls onnodeclick with the clicked node once the dblclick window passes', async () => {
    vi.useFakeTimers();
    const onnodeclick = vi.fn();
    const { getByText } = render(TreeDiagram, {
      slice,
      onnodeclick,
      onnodedblclick: vi.fn(),
    });

    await fireEvent.click(getByText('father (en)').closest('.node')!);
    expect(onnodeclick).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(300);

    expect(onnodeclick).toHaveBeenCalledOnce();
    expect(onnodeclick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'a1', headword: 'father' }),
    );
    vi.useRealTimers();
  });

  it('calls onnodedblclick and suppresses the pending onnodeclick', async () => {
    vi.useFakeTimers();
    const onnodeclick = vi.fn();
    const onnodedblclick = vi.fn();
    const { getByText } = render(TreeDiagram, {
      slice,
      onnodeclick,
      onnodedblclick,
    });
    const node = getByText('father (en)').closest('.node')!;

    await fireEvent.click(node);
    await fireEvent.dblClick(node);
    await vi.advanceTimersByTimeAsync(300);

    expect(onnodedblclick).toHaveBeenCalledOnce();
    expect(onnodedblclick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'a1', headword: 'father' }),
    );
    expect(onnodeclick).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('opens the detail panel via Enter/Space with no dblclick delay', async () => {
    const onnodeclick = vi.fn();
    const { getByText } = render(TreeDiagram, {
      slice,
      onnodeclick,
      onnodedblclick: vi.fn(),
    });

    await fireEvent.keyDown(getByText('father (en)').closest('.node')!, {
      key: 'Enter',
    });

    expect(onnodeclick).toHaveBeenCalledOnce();
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
      ...baseHandlers(),
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
      ...baseHandlers(),
    });

    expect(container.querySelectorAll('line.edge')).toHaveLength(2);
    expect(container.querySelectorAll('path.edge.cross-link')).toHaveLength(
      1,
    );
  });

  it('shows a "+N more" affordance when a fan-out exceeds the cap', () => {
    const { container, getByText } = render(TreeDiagram, {
      slice: wideFanoutSlice(),
      ...baseHandlers(),
    });

    expect(getByText('+5 more')).toBeInTheDocument();
    expect(container.querySelectorAll('.node.overflow')).toHaveLength(1);
    expect(container.querySelectorAll('.node:not(.overflow)')).toHaveLength(
      MAX_SIBLINGS_PER_PARENT + 1,
    );
  });

  it('reveals the rest of a capped fan-out on click, dropping the affordance', async () => {
    const { container, getByText, queryByText } = render(TreeDiagram, {
      slice: wideFanoutSlice(),
      ...baseHandlers(),
    });

    await fireEvent.click(getByText('+5 more'));

    expect(queryByText('+5 more')).not.toBeInTheDocument();
    expect(container.querySelectorAll('.node')).toHaveLength(
      MAX_SIBLINGS_PER_PARENT + 5 + 1,
    );
  });

  it('resets a revealed fan-out when the slice changes', async () => {
    const { getByText, queryByText, rerender } = render(TreeDiagram, {
      slice: wideFanoutSlice(),
      ...baseHandlers(),
    });
    await fireEvent.click(getByText('+5 more'));
    expect(queryByText('+5 more')).not.toBeInTheDocument();

    await rerender({ slice: wideFanoutSlice(), ...baseHandlers() });

    expect(getByText('+5 more')).toBeInTheDocument();
  });

  it('widens the rect for a node whose label is longer than the floor width', () => {
    const longHeadword = 'a'.repeat(40);
    const longSlice: TreeSlice = {
      focusId: 'f',
      nodes: [
        {
          id: 'f',
          langCode: 'en',
          headword: longHeadword,
          isReconstructed: false,
          depth: 0,
        },
      ],
      edges: [],
    };

    const { getByText } = render(TreeDiagram, {
      slice: longSlice,
      ...baseHandlers(),
    });
    const rect = getByText(`${longHeadword} (en)`)
      .closest('.node')!
      .querySelector('rect')!;

    expect(Number(rect.getAttribute('width'))).toBeGreaterThan(120);
  });

  it('keeps a short-headword node rect at the floor width', () => {
    const { getByText } = render(TreeDiagram, { slice, ...baseHandlers() });
    const rect = getByText('grandfather (en)')
      .closest('.node')!
      .querySelector('rect')!;

    expect(Number(rect.getAttribute('width'))).toBe(120);
  });
});
