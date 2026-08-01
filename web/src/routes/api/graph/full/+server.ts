import type { RequestHandler } from './$types';
import { fullGraph } from '$lib/server/queries';
import { encodeViewportTile } from '$lib/binaryTile';

// GET /api/graph/full
// Returns the structure tier (nodes + edges, no bounding box or cap)
// for the entire graph -- the whole-graph overview's one-shot fetch.
// Binary, not JSON, for the same reason as /api/viewport (see
// ETYM-70): a JSON encoding of the full graph exceeds V8's string
// length limit.
export const GET: RequestHandler = async () => {
  const tile = await fullGraph();
  return new Response(encodeViewportTile(tile), {
    headers: { 'Content-Type': 'application/octet-stream' },
  });
};
