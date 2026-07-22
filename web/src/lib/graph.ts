import Graph from 'graphology';
import type { ViewportTile } from './types';

export type Theme = 'light' | 'dark';

// Kept in sync with the CSS custom properties in theme.css: focus/node
// mirror --focus/--accent, edge/label mirror --tx-3/--tx.
const THEME_COLORS: Record<
  Theme,
  { focus: string; node: string; edge: string; label: string }
> = {
  light: {
    focus: '#af3029',
    node: '#205ea6',
    edge: '#b7b5ac',
    label: '#100f0f',
  },
  dark: {
    focus: '#d14d41',
    node: '#4385be',
    edge: '#575653',
    label: '#cecdc3',
  },
};

export function canvasColors(theme: Theme) {
  return THEME_COLORS[theme];
}

const FOCUS_SIZE = 12;
const NODE_SIZE = 6;

// Converts one viewport tile into a graphology graph Sigma can render.
// Node positions come straight from the server's precomputed layout
// (ETYM-67/69) -- no client-side jitter. Tile nodes carry no
// headword/langCode/gloss text (ETYM-70's structure/attribute split),
// so no label is set here; hovering or clicking a node fetches that
// lazily (see the /graph/[lang]/[headword] page).
export function buildGraph(
  tile: ViewportTile,
  focusId: string,
  theme: Theme = 'light',
): Graph {
  // multi: true because two lexemes can be linked by more than one
  // rel_type (e.g. both "derived" and "cognate" are separate DB rows).
  const graph = new Graph({ type: 'directed', multi: true });
  const { focus, node: nodeColor } = THEME_COLORS[theme];

  tile.nodes.forEach((node) => {
    const isFocus = node.id === focusId;
    graph.addNode(node.id, {
      degree: node.degree,
      size: isFocus ? FOCUS_SIZE : NODE_SIZE,
      color: isFocus ? focus : nodeColor,
      x: node.x,
      y: node.y,
    });
  });

  for (const edge of tile.edges) {
    graph.addEdge(edge.srcId, edge.dstId, {
      label: edge.relType,
      size: 1,
    });
  }

  return graph;
}
