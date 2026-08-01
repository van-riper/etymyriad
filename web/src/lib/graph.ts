import type { ViewportTile } from './types';

export type Theme = 'light' | 'dark';

// Kept in sync with the CSS custom properties in theme.css: focus/node
// mirror --focus/--accent, edge/label mirror --tx-3/--tx, bg mirrors
// --bg (cosmos.gl's canvas defaults to an opaque #222222 background,
// unlike sigma.js which left the container's CSS background visible).
const THEME_COLORS: Record<
  Theme,
  { focus: string; node: string; edge: string; label: string; bg: string }
> = {
  light: {
    focus: '#af3029',
    node: '#205ea6',
    edge: '#b7b5ac',
    label: '#100f0f',
    bg: '#fffcf0',
  },
  dark: {
    focus: '#d14d41',
    node: '#4385be',
    edge: '#575653',
    label: '#cecdc3',
    bg: '#100f0f',
  },
};

export function canvasColors(theme: Theme) {
  return THEME_COLORS[theme];
}

const FOCUS_SIZE = 12;
const NODE_SIZE = 6;

function hexToRgba(hex: string): [number, number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  return [r, g, b, 1];
}

// cosmos.gl points/links are addressed by array index, not string id,
// so the caller (the graph page) needs `ids[index]` to resolve a
// clicked/hovered point back to a lexeme id.
export interface CosmosGraphData {
  ids: string[];
  positions: Float32Array;
  colors: Float32Array;
  sizes: Float32Array;
  links: Float32Array;
  linkColors: Float32Array;
}

// Converts one viewport tile into cosmos.gl's flat data arrays. Node
// positions come straight from the server's precomputed layout
// (ETYM-67/69) -- no client-side jitter. Tile nodes carry no
// headword/langCode/gloss text (ETYM-70's structure/attribute split),
// so hovering or clicking a node fetches that lazily (see the
// /graph/[lang]/[headword] page).
export function buildGraph(
  tile: ViewportTile,
  focusId: string | null,
  theme: Theme = 'light',
): CosmosGraphData {
  const { focus, node: nodeColor, edge: edgeColor } = THEME_COLORS[theme];
  const focusRgba = hexToRgba(focus);
  const nodeRgba = hexToRgba(nodeColor);
  const edgeRgba = hexToRgba(edgeColor);

  const ids: string[] = new Array(tile.nodes.length);
  const indexById = new Map<string, number>();
  const positions = new Float32Array(tile.nodes.length * 2);
  const colors = new Float32Array(tile.nodes.length * 4);
  const sizes = new Float32Array(tile.nodes.length);

  tile.nodes.forEach((node, i) => {
    ids[i] = node.id;
    indexById.set(node.id, i);
    positions[i * 2] = node.x;
    positions[i * 2 + 1] = node.y;
    const isFocus = node.id === focusId;
    sizes[i] = isFocus ? FOCUS_SIZE : NODE_SIZE;
    const rgba = isFocus ? focusRgba : nodeRgba;
    colors.set(rgba, i * 4);
  });

  const links = new Float32Array(tile.edges.length * 2);
  const linkColors = new Float32Array(tile.edges.length * 4);
  tile.edges.forEach((edge, i) => {
    // Every edge's endpoints are guaranteed present in this same
    // tile's node list -- the server returns them together.
    links[i * 2] = indexById.get(edge.srcId)!;
    links[i * 2 + 1] = indexById.get(edge.dstId)!;
    linkColors.set(edgeRgba, i * 4);
  });

  return { ids, positions, colors, sizes, links, linkColors };
}
