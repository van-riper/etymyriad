<script lang="ts">
  import { layoutTree, NODE_WIDTH, NODE_HEIGHT } from '../utils/treeLayout';
  import type { TreeNode, TreeSlice } from '../types';

  let {
    slice,
    onnodeclick,
  }: {
    slice: TreeSlice;
    onnodeclick: (node: TreeNode) => void;
  } = $props();

  const layout = $derived(layoutTree(slice));
</script>

<svg
  viewBox="{layout.viewBox.minX} {layout.viewBox.minY} {layout.viewBox
    .width} {layout.viewBox.height}"
  role="img"
  aria-label="Etymology tree"
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
      onclick={() => onnodeclick(node)}
      onkeydown={(event) => {
        if (event.key === 'Enter' || event.key === ' ')
          onnodeclick(node);
      }}
    >
      <rect
        x={node.x - NODE_WIDTH / 2}
        y={node.y - NODE_HEIGHT / 2}
        width={NODE_WIDTH}
        height={NODE_HEIGHT}
        rx="6"
      />
      <text x={node.x} y={node.y} text-anchor="middle" dominant-baseline="middle"
        >{node.headword} ({node.langCode})</text
      >
    </g>
  {/each}
</svg>

<style>
  svg {
    display: block;
    width: 100%;
    height: 100%;
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
</style>
