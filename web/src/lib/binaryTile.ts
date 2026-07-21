// Binary wire format for the structure tier (see ETYM-70). A JSON
// ViewportTile of the full graph runs ~1GB (2M nodes + 3M edges) and
// exceeds V8's string length limit; this encodes the same data as a
// compact ArrayBuffer instead, with edges referencing nodes by index
// rather than by UUID.
import type { LayoutEdge, LayoutNode, RelType, ViewportTile } from './types';

// Order is the wire-format enum; must never be reordered once deployed
// (it would silently reinterpret every already-encoded byte).
const REL_TYPES: RelType[] = [
  'inherited',
  'borrowed',
  'learned_borrowing',
  'semi_learned_borrowing',
  'derived',
  'root',
  'affix',
  'compound',
  'calque',
  'cognate',
  'mention',
  'onomatopoeic',
];

const NODE_RECORD_BYTES = 16 + 4 + 4 + 4; // uuid + x + y + degree
const EDGE_RECORD_BYTES = 4 + 4 + 1; // srcIdx + dstIdx + relType

function uuidToBytes(uuid: string): Uint8Array {
  const hex = uuid.replace(/-/g, '');
  const bytes = new Uint8Array(16);
  for (let i = 0; i < 16; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

function bytesToUuid(bytes: Uint8Array): string {
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join(
    '',
  );
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join('-');
}

export function encodeViewportTile(tile: ViewportTile): ArrayBuffer {
  const indexById = new Map<string, number>();
  tile.nodes.forEach((node, i) => indexById.set(node.id, i));

  const byteLength =
    8 +
    tile.nodes.length * NODE_RECORD_BYTES +
    tile.edges.length * EDGE_RECORD_BYTES;
  const buffer = new ArrayBuffer(byteLength);
  const view = new DataView(buffer);
  let offset = 0;

  view.setUint32(offset, tile.nodes.length);
  offset += 4;
  view.setUint32(offset, tile.edges.length);
  offset += 4;

  for (const node of tile.nodes) {
    new Uint8Array(buffer, offset, 16).set(uuidToBytes(node.id));
    offset += 16;
    view.setFloat32(offset, node.x);
    offset += 4;
    view.setFloat32(offset, node.y);
    offset += 4;
    view.setUint32(offset, node.degree);
    offset += 4;
  }

  for (const edge of tile.edges) {
    const srcIdx = indexById.get(edge.srcId);
    const dstIdx = indexById.get(edge.dstId);
    if (srcIdx === undefined || dstIdx === undefined) {
      throw new Error(
        `edge references a node id outside this tile: ${edge.srcId} -> ${edge.dstId}`,
      );
    }
    view.setUint32(offset, srcIdx);
    offset += 4;
    view.setUint32(offset, dstIdx);
    offset += 4;
    view.setUint8(offset, REL_TYPES.indexOf(edge.relType));
    offset += 1;
  }

  return buffer;
}

export function decodeViewportTile(buffer: ArrayBuffer): ViewportTile {
  const view = new DataView(buffer);
  let offset = 0;

  const numNodes = view.getUint32(offset);
  offset += 4;
  const numEdges = view.getUint32(offset);
  offset += 4;

  const nodes: LayoutNode[] = [];
  for (let i = 0; i < numNodes; i++) {
    const id = bytesToUuid(new Uint8Array(buffer, offset, 16));
    offset += 16;
    const x = view.getFloat32(offset);
    offset += 4;
    const y = view.getFloat32(offset);
    offset += 4;
    const degree = view.getUint32(offset);
    offset += 4;
    nodes.push({ id, x, y, degree });
  }

  const edges: LayoutEdge[] = [];
  for (let i = 0; i < numEdges; i++) {
    const srcIdx = view.getUint32(offset);
    offset += 4;
    const dstIdx = view.getUint32(offset);
    offset += 4;
    const relType = REL_TYPES[view.getUint8(offset)];
    offset += 1;
    edges.push({ srcId: nodes[srcIdx].id, dstId: nodes[dstIdx].id, relType });
  }

  return { nodes, edges };
}
