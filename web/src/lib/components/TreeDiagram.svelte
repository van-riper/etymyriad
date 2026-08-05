<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { select } from 'd3-selection';
  import { zoom as d3zoom, zoomIdentity } from 'd3-zoom';
  import type { D3ZoomEvent } from 'd3-zoom';
  import { layoutTree, NODE_WIDTH, NODE_HEIGHT } from '../utils/treeLayout';
  import { computeFitTransform, FLOOR_SCALE } from '../utils/zoomFit';
  import { displayHeadword } from '../utils/headword';
  import type { TreeNode, TreeSlice } from '../types';

  let {
    slice,
    onnodeclick,
  }: {
    slice: TreeSlice;
    onnodeclick: (node: TreeNode) => void;
  } = $props();

  // Which parents' "+N more" cap the user has clicked past. Reset on
  // every new slice, since a prior focus word's expansions have no
  // bearing on the new one. Plain (non-reactive) reference, not
  // $state -- wrapping it in $state would proxy the assigned slice,
  // so it could never again compare equal to the raw prop and this
  // effect would retrigger itself forever.
  let expandedParents = $state(new Set<string>());
  let expandedForSlice: TreeSlice | undefined;
  $effect(() => {
    if (slice !== expandedForSlice) {
      expandedForSlice = slice;
      expandedParents = new Set();
    }
  });

  const layout = $derived(layoutTree(slice, expandedParents));

  let svgEl: SVGSVGElement;
  let transform = $state(zoomIdentity);
  const zoomBehavior = d3zoom<SVGSVGElement, unknown>().scaleExtent([
    FLOOR_SCALE,
    8,
  ]);

  onMount(() => {
    // d3-zoom's default extent reads the svg's viewBox/width.baseVal,
    // which we don't set (the zoom-layer's own transform handles all
    // scaling) and jsdom doesn't implement for an attribute-less
    // <svg> -- so extent is derived from clientWidth/clientHeight
    // directly instead of the SVG geometry properties.
    zoomBehavior.extent(function (this: SVGSVGElement) {
      return [
        [0, 0],
        [this.clientWidth, this.clientHeight],
      ] as [[number, number], [number, number]];
    });
    zoomBehavior.on(
      'zoom',
      (event: D3ZoomEvent<SVGSVGElement, unknown>) =>
        (transform = event.transform),
    );
    select(svgEl).call(zoomBehavior);
  });

  onDestroy(() => {
    select(svgEl).on('.zoom', null);
  });

  // Re-fit whenever the focus word changes (a new layout), clamped so
  // a tree too large to fit at FLOOR_SCALE starts partly off-screen
  // rather than shrinking further -- pan/zoom reaches the rest.
  $effect(() => {
    if (!svgEl) return;
    const fit = computeFitTransform(
      layout.viewBox,
      svgEl.clientWidth,
      svgEl.clientHeight,
    );
    zoomBehavior.transform(
      select(svgEl),
      zoomIdentity.translate(fit.x, fit.y).scale(fit.k),
    );
  });
</script>

<svg bind:this={svgEl} role="img" aria-label="Etymology tree">
  <g
    class="zoom-layer"
    transform="translate({transform.x},{transform.y}) scale({transform.k})"
  >
    {#each layout.edges as edge (edge.srcId + ':' + edge.dstId)}
      {@const src = layout.nodes.find((n) => n.id === edge.srcId)}
      {@const dst = layout.nodes.find((n) => n.id === edge.dstId)}
      {#if src && dst}
        <line
          class="edge"
          class:cross-link={edge.kind === 'cross-link'}
          x1={src.x}
          y1={src.y}
          x2={dst.x}
          y2={dst.y}
        />
      {/if}
    {/each}
    {#each layout.nodes as node (node.id)}
      {@const label = displayHeadword(node.headword, node.isReconstructed)}
      <g
        class="node"
        class:focus={node.isFocus}
        role="button"
        tabindex="0"
        onclick={() => onnodeclick(node)}
        onkeydown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') onnodeclick(node);
        }}
      >
        <rect
          x={node.x - NODE_WIDTH / 2}
          y={node.y - NODE_HEIGHT / 2}
          width={NODE_WIDTH}
          height={NODE_HEIGHT}
          rx="6"
        />
        <text
          x={node.x}
          y={node.y}
          text-anchor="middle"
          dominant-baseline="middle">{label} ({node.langCode})</text
        >
      </g>
    {/each}
    {#each layout.overflow as entry (entry.parentId)}
      <g
        class="node overflow"
        role="button"
        tabindex="0"
        onclick={() =>
          (expandedParents = new Set([...expandedParents, entry.parentId]))}
        onkeydown={(event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return;
          expandedParents = new Set([...expandedParents, entry.parentId]);
        }}
      >
        <rect
          x={entry.x - NODE_WIDTH / 2}
          y={entry.y - NODE_HEIGHT / 2}
          width={NODE_WIDTH}
          height={NODE_HEIGHT}
          rx="6"
        />
        <text
          x={entry.x}
          y={entry.y}
          text-anchor="middle"
          dominant-baseline="middle">+{entry.count} more</text
        >
      </g>
    {/each}
  </g>
</svg>

<style>
  svg {
    display: block;
    width: 100%;
    height: 100%;
    cursor: grab;
    touch-action: none;
  }
  .edge {
    stroke: var(--tx-2);
    stroke-width: 1.5;
  }
  .edge.cross-link {
    stroke: var(--tx-3);
    stroke-dasharray: 4 3;
  }
  .node {
    cursor: pointer;
  }
  .node rect {
    fill: var(--bg-2);
    stroke: var(--ui-border);
  }
  .node text {
    fill: var(--tx);
    font-size: 0.75rem;
  }
  .node.focus rect {
    fill: var(--focus);
    stroke: var(--focus);
  }
  .node.focus text {
    fill: var(--bg);
  }
  .node.overflow rect {
    fill: none;
    stroke-dasharray: 4 3;
  }
  .node.overflow text {
    fill: var(--tx-2);
  }
</style>
