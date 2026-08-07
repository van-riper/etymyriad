<script lang="ts">
  import { onMount, onDestroy, untrack } from 'svelte';
  import { select } from 'd3-selection';
  import { zoom as d3zoom, zoomIdentity } from 'd3-zoom';
  import type { D3ZoomEvent } from 'd3-zoom';
  import { toast } from 'svelte-sonner';
  import {
    layoutTree,
    NODE_HEIGHT,
    type OverflowNode,
  } from '../utils/treeLayout';
  import {
    mergeTreeExpansion,
    type TreeExpansion,
  } from '../utils/mergeExpansion';
  import { computeFitTransform, FLOOR_SCALE } from '../utils/zoomFit';
  import { apiFetch } from '../utils/apiFetch';
  import type { TreeNode, TreeSlice } from '../types';

  let {
    slice,
    onnodeclick,
    onnodedblclick,
  }: {
    slice: TreeSlice;
    onnodeclick: (node: TreeNode) => void;
    onnodedblclick: (node: TreeNode) => void;
  } = $props();

  // A local, growable copy of the prop: expanding a "+N more" fetches
  // more of the tree (ETYM-144) and merges it in, which the prop
  // itself can't hold since it's owned by the page load. Reset on
  // every new slice, since a prior focus word's expansions have no
  // bearing on the new one. syncedForSlice is a plain (non-reactive)
  // reference, not $state -- wrapping it in $state would proxy the
  // assigned slice, so it could never again compare equal to the raw
  // prop and this effect would retrigger itself forever.
  let currentSlice = $state(untrack(() => slice));
  let expandedParents = $state(new Set<string>());
  let syncedForSlice: TreeSlice | undefined;
  // Consumed by the re-fit effect below to toast "too many nodes"
  // exactly once per focus-word navigation, not on every later re-fit
  // (e.g. expanding a capped fan-out also changes layout.viewBox).
  let pendingFitToast = false;
  $effect(() => {
    if (slice !== syncedForSlice) {
      syncedForSlice = slice;
      currentSlice = slice;
      expandedParents = new Set();
      pendingFitToast = true;
    }
  });

  const layout = $derived(layoutTree(currentSlice, expandedParents));

  // Reveals a capped parent's overflow. If every overflowed child is
  // already present in currentSlice (the server never capped the
  // fetch itself, or everything's already been fetched by an earlier
  // expand), there's nothing to fetch -- just lift the local cap. If
  // the server reported more than what's present, some of it was
  // never fetched at all (ETYM-144); fetch exactly that next batch,
  // scoped to this parent, rather than re-fetching anything already
  // known.
  async function expandOverflow(entry: OverflowNode) {
    const hasUnfetched = (currentSlice.overflow ?? []).some(
      (o) => o.parentId === entry.parentId && o.direction === entry.direction,
    );
    if (!hasUnfetched) {
      expandedParents = new Set([...expandedParents, entry.parentId]);
      return;
    }

    const parent = currentSlice.nodes.find((n) => n.id === entry.parentId);
    if (!parent) return;

    const knownChildIds =
      entry.direction === 'descendant'
        ? currentSlice.edges
            .filter((e) => e.srcId === entry.parentId)
            .map((e) => e.dstId)
        : currentSlice.edges
            .filter((e) => e.dstId === entry.parentId)
            .map((e) => e.srcId);

    const qs = new URLSearchParams({
      dir: entry.direction,
      depth: String(parent.depth),
      ...(knownChildIds.length > 0 && { exclude: knownChildIds.join(',') }),
    });

    try {
      const response = await apiFetch(
        `/api/trees/${entry.parentId}/expand?${qs}`,
      );
      if (!response.ok) return;
      const expansion = (await response.json()) as TreeExpansion;
      currentSlice = mergeTreeExpansion(
        currentSlice,
        entry.parentId,
        entry.direction,
        expansion,
      );
      expandedParents = new Set([...expandedParents, entry.parentId]);
    } catch (err) {
      console.error('Failed to expand tree node:', err);
    }
  }

  // Browsers fire `click` before `dblclick`, so a same-node
  // double-click would otherwise flash the detail panel open right
  // before onnodedblclick navigates away. Delay the single-click
  // action by the platform dblclick threshold and let a following
  // dblclick cancel it.
  const DBLCLICK_THRESHOLD_MS = 300;
  let pendingClick: ReturnType<typeof setTimeout> | undefined;

  function handleNodeClick(node: TreeNode) {
    clearTimeout(pendingClick);
    pendingClick = setTimeout(() => onnodeclick(node), DBLCLICK_THRESHOLD_MS);
  }

  function handleNodeDblClick(node: TreeNode) {
    clearTimeout(pendingClick);
    onnodedblclick(node);
  }

  let svgEl: SVGSVGElement;
  let transform = $state(zoomIdentity);
  // 8 is how far a user can zoom in by hand, separate from
  // computeFitTransform's own (much lower) auto-fit ceiling.
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
    // d3-zoom binds its own double-click-to-zoom handler by default,
    // which calls stopImmediatePropagation and would otherwise
    // swallow a node's dblclick before it bubbles to the delegated
    // onnodedblclick listener.
    select(svgEl).call(zoomBehavior).on('dblclick.zoom', null);
  });

  onDestroy(() => {
    select(svgEl).on('.zoom', null);
    clearTimeout(pendingClick);
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
    if (pendingFitToast) {
      pendingFitToast = false;
      if (fit.clamped) {
        toast.info(
          'This tree has too many nodes to fit on screen. Pan or zoom to see the rest.',
        );
      }
    }
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
      <g
        class="node"
        class:focus={node.isFocus}
        role="button"
        tabindex="0"
        onclick={() => handleNodeClick(node)}
        ondblclick={() => handleNodeDblClick(node)}
        onkeydown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') onnodeclick(node);
        }}
      >
        <rect
          x={node.x - node.width / 2}
          y={node.y - NODE_HEIGHT / 2}
          width={node.width}
          height={NODE_HEIGHT}
          rx="6"
        />
        <text
          x={node.x}
          y={node.y}
          text-anchor="middle"
          dominant-baseline="middle">{node.label}</text
        >
      </g>
    {/each}
    {#each layout.overflow as entry (entry.parentId)}
      <g
        class="node overflow"
        role="button"
        tabindex="0"
        onclick={() => expandOverflow(entry)}
        onkeydown={(event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return;
          expandOverflow(entry);
        }}
      >
        <rect
          x={entry.x - entry.width / 2}
          y={entry.y - NODE_HEIGHT / 2}
          width={entry.width}
          height={NODE_HEIGHT}
          rx="6"
        />
        <text
          x={entry.x}
          y={entry.y}
          text-anchor="middle"
          dominant-baseline="middle">{entry.label}</text
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
