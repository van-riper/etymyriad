<!-- web/src/lib/GraphCanvas.svelte -->
<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { Graph as CosmosGraph } from '@cosmos.gl/graph';
  import { buildGraph, canvasColors, type Theme } from './graph';
  import type { ViewportTile } from './types';

  let {
    tile,
    focusId,
    theme,
    onnodeclick,
    onnodehover,
    onhoverend,
  }: {
    tile: ViewportTile;
    focusId: string | null;
    theme: Theme;
    onnodeclick: (id: string) => void;
    onnodehover: (id: string, x: number, y: number) => void;
    onhoverend: () => void;
  } = $props();

  let container: HTMLDivElement = $state()!;
  let renderer: CosmosGraph | null = null;
  // Monotonic guard: lets a stale in-flight render detect it's been
  // superseded (a new tile/theme arrived) before it touches `renderer`.
  let renderGen = 0;

  export function fitView() {
    renderer?.fitView();
  }

  // cosmos.gl needs WebGL, which only exists in the browser -- a
  // static import would crash SvelteKit's SSR render, so it's loaded
  // lazily here.
  async function renderNetwork() {
    const gen = ++renderGen;
    renderer?.destroy();
    renderer = null;
    const { Graph } = await import('@cosmos.gl/graph');
    if (gen !== renderGen) return;
    const colors = canvasColors(theme);
    const data = buildGraph(tile, focusId, theme);

    renderer = new Graph(container, {
      backgroundColor: colors.bg,
      enableSimulation: false,
      // Undefined (the default) makes cosmos.gl continuously refit
      // points to the visible space when simulation is off, which
      // reads as a perpetual downward drift. DrL's real coordinates
      // already fit inside the default 4096-unit space (ETYM-77's
      // spike), so no rescale is needed.
      rescalePositions: false,
      onPointClick: (index) => onnodeclick(data.ids[index]),
      onPointMouseOver: (index, _pointPosition, event) => {
        // Hover can also fire from panning a stationary mouse over a
        // moving point (a D3 zoom/drag event), not just real mouse
        // movement -- points never move here (enableSimulation is
        // false), so only a real MouseEvent carries a tooltip position.
        if (!(event instanceof MouseEvent)) return;
        const rect = container.getBoundingClientRect();
        onnodehover(
          data.ids[index],
          event.clientX - rect.left,
          event.clientY - rect.top,
        );
      },
      onPointMouseOut: () => onhoverend(),
    });
    renderer.setPointPositions(data.positions);
    renderer.setPointColors(data.colors);
    renderer.setPointSizes(data.sizes);
    renderer.setLinks(data.links);
    renderer.setLinkColors(data.linkColors);
    renderer.render(0);
  }

  $effect(() => {
    // Synchronously read every prop this effect depends on so Svelte
    // re-tracks them as dependencies -- renderNetwork's own reads of
    // them happen after an `await`, too late for the tracking window.
    void tile;
    void focusId;
    void theme;
    void renderNetwork();
  });

  onDestroy(() => {
    renderer?.destroy();
  });
</script>

<div class="canvas" bind:this={container}></div>

<style>
  .canvas {
    width: 100%;
    height: 100%;
    background: var(--bg);
  }
</style>
