import Graph from 'graphology';
import type { EgoNetwork } from './types';

const FOCUS_COLOR = '#e04040';
const NODE_COLOR = '#4070e0';

// Hop distance from the focus node, ignoring edge direction (an ancestor
// and a descendant one step away are equally "close"). Ego-networks are
// built server-side by BFS from the same focus, so every node should be
// reachable; a node that somehow isn't still renders, one ring past the
// farthest reachable one, rather than crashing.
function distancesFromFocus(network: EgoNetwork): Map<string, number> {
  const neighbors = new Map<string, string[]>();
  for (const node of network.nodes) neighbors.set(node.id, []);
  for (const edge of network.edges) {
    neighbors.get(edge.srcId)?.push(edge.dstId);
    neighbors.get(edge.dstId)?.push(edge.srcId);
  }

  const distance = new Map<string, number>([[network.focusId, 0]]);
  const queue = [network.focusId];
  for (let i = 0; i < queue.length; i++) {
    const id = queue[i];
    const d = distance.get(id)!;
    for (const neighbor of neighbors.get(id) ?? []) {
      if (distance.has(neighbor)) continue;
      distance.set(neighbor, d + 1);
      queue.push(neighbor);
    }
  }

  const maxDistance = Math.max(0, ...distance.values());
  for (const node of network.nodes) {
    if (!distance.has(node.id)) distance.set(node.id, maxDistance + 1);
  }
  return distance;
}

// Converts one ego-network response into a graphology graph Sigma can
// render. Nodes sit on concentric rings by hop distance from the focus
// word (ring 0 = focus, ring 1 = direct neighbors, ...), spread evenly by
// angle within each ring; ponytail: swap in graphology-layout-forceatlas2
// if rings still tangle for very dense words.
export function buildGraph(network: EgoNetwork): Graph {
  // multi: true because two lexemes can be linked by more than one
  // rel_type (e.g. both "derived" and "cognate" are separate DB rows).
  const graph = new Graph({ type: 'directed', multi: true });
  const distance = distancesFromFocus(network);

  const ringCounts = new Map<number, number>();
  for (const d of distance.values()) {
    ringCounts.set(d, (ringCounts.get(d) ?? 0) + 1);
  }
  const ringSeen = new Map<number, number>();

  network.nodes.forEach((node) => {
    const ring = distance.get(node.id)!;
    const i = ringSeen.get(ring) ?? 0;
    ringSeen.set(ring, i + 1);
    const angle = (2 * Math.PI * i) / (ringCounts.get(ring) ?? 1);

    graph.addNode(String(node.id), {
      label: `${node.headword} (${node.langCode})`,
      headword: node.headword,
      langCode: node.langCode,
      size: node.id === network.focusId ? 12 : 6,
      color: node.id === network.focusId ? FOCUS_COLOR : NODE_COLOR,
      x: ring * Math.cos(angle),
      y: ring * Math.sin(angle),
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
