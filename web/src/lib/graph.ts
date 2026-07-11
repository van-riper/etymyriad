import Graph from 'graphology';
import type { EgoNetwork } from './types';

const FOCUS_COLOR = '#e04040';
const NODE_COLOR = '#4070e0';

// Converts one ego-network response into a graphology graph Sigma can
// render. Nodes get a circular layout since no layout package is
// installed; ponytail: swap in graphology-layout-forceatlas2 if dense
// ego-networks need untangling.
export function buildGraph(network: EgoNetwork): Graph {
  // multi: true because two lexemes can be linked by more than one
  // rel_type (e.g. both "derived" and "cognate" are separate DB rows).
  const graph = new Graph({ type: 'directed', multi: true });
  const n = network.nodes.length;

  network.nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / n;
    graph.addNode(String(node.id), {
      label: `${node.headword} (${node.langCode})`,
      headword: node.headword,
      langCode: node.langCode,
      size: node.id === network.focusId ? 12 : 6,
      color: node.id === network.focusId ? FOCUS_COLOR : NODE_COLOR,
      x: Math.cos(angle),
      y: Math.sin(angle),
    });
  });

  for (const edge of network.edges) {
    graph.addEdge(String(edge.srcId), String(edge.dstId), {
      label: edge.relType,
      size: 1,
    });
  }

  return graph;
}
