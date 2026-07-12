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

// World-unit radius contributed per sqrt(node count) in a ring. Using
// sqrt(count) rather than count keeps radius growth closer to how area
// (not circumference) scales with node count -- a ring with hundreds of
// nodes still stays close to the focus instead of ballooning outward and
// leaving a dead gap near the center. Heuristic, not measured against
// real label pixel sizes.
const RADIUS_PER_SQRT_NODE = 0.4;

// Minimum radius gap enforced between consecutive rings, so a sparse
// ring can't sit at (or inside) the same radius as a denser nearer one.
const RING_GAP = 0.5;

// Exponent that compresses inner rings toward the focus relative to the
// outermost ring. Sigma auto-fits the camera to the largest ring
// regardless of absolute scale, so a near ring that's itself crowded
// (sqrt(count) alone still pushes it out almost as far as a farther,
// denser ring) leaves a dead gap around the focus unless inner radii
// are pulled in disproportionately, not just uniformly rescaled.
const RADIUS_GAMMA = 2.5;

// Radius per hop distance: at least the hop distance itself (so rings
// stay roughly ordered by distance), at least enough room for a crowded
// ring's node count, and always past the previous ring's radius. The
// result is then gamma-compressed toward the focus (see RADIUS_GAMMA).
function ringRadii(ringCounts: Map<number, number>): Map<number, number> {
  const radii = new Map<number, number>([[0, 0]]);
  const rings = [...ringCounts.keys()]
    .filter((d) => d > 0)
    .sort((a, b) => a - b);

  let prev = 0;
  for (const d of rings) {
    const minForCount = RADIUS_PER_SQRT_NODE * Math.sqrt(ringCounts.get(d)!);
    const radius = Math.max(d, minForCount, prev + RING_GAP);
    radii.set(d, radius);
    prev = radius;
  }

  const maxRadius = Math.max(0, ...radii.values());
  if (maxRadius === 0) return radii;
  for (const [d, radius] of radii) {
    radii.set(d, maxRadius * (radius / maxRadius) ** RADIUS_GAMMA);
  }
  return radii;
}

// Deterministic pseudo-random value in [0, 1) for a string (FNV-1a
// hash). Jitter needs to look organic but stay put across re-renders of
// the same network, which rules out Math.random().
function hash01(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 10000) / 10000;
}

// Fraction of a node's angular slot, and of its ring's radius, that
// per-node jitter can shift it by -- breaks up the "every node on one
// exact circle" look without needing a full physics layout.
const ANGLE_JITTER = 0.6;
const RADIUS_JITTER = 0.25;

// Converts one ego-network response into a graphology graph Sigma can
// render. Nodes sit on concentric rings by hop distance from the focus
// word (ring 0 = focus, ring 1 = direct neighbors, ...), spread by angle
// within each ring with deterministic per-node jitter on both angle and
// radius, and ring radius growing with sqrt(node count) rather than a
// fixed hop-distance multiple; ponytail: swap in
// graphology-layout-forceatlas2 if rings still tangle for very dense
// words.
export function buildGraph(network: EgoNetwork): Graph {
  // multi: true because two lexemes can be linked by more than one
  // rel_type (e.g. both "derived" and "cognate" are separate DB rows).
  const graph = new Graph({ type: 'directed', multi: true });
  const distance = distancesFromFocus(network);

  const ringCounts = new Map<number, number>();
  for (const d of distance.values()) {
    ringCounts.set(d, (ringCounts.get(d) ?? 0) + 1);
  }
  const radiusByRing = ringRadii(ringCounts);
  const ringSeen = new Map<number, number>();

  network.nodes.forEach((node) => {
    const ring = distance.get(node.id)!;
    const i = ringSeen.get(ring) ?? 0;
    ringSeen.set(ring, i + 1);
    const angleStep = (2 * Math.PI) / (ringCounts.get(ring) ?? 1);
    const angle =
      angleStep * i +
      (hash01(`${node.id}:angle`) - 0.5) * angleStep * ANGLE_JITTER;
    const radius =
      radiusByRing.get(ring)! *
      (1 + (hash01(`${node.id}:radius`) - 0.5) * 2 * RADIUS_JITTER);
    const isFocus = node.id === network.focusId;

    graph.addNode(String(node.id), {
      label: `${node.headword} (${node.langCode})`,
      headword: node.headword,
      langCode: node.langCode,
      size: isFocus ? 12 : 6,
      color: isFocus ? FOCUS_COLOR : NODE_COLOR,
      x: isFocus ? 0 : radius * Math.cos(angle),
      y: isFocus ? 0 : radius * Math.sin(angle),
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
