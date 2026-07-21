import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { viewportTile } from '$lib/server/queries';
import { encodeViewportTile } from '$lib/binaryTile';

// Parses a required numeric query param. Returns null if missing or
// not a finite number -- distinct from `Number(null) === 0`, which
// would silently accept an absent param as a valid zero bound.
function parseRequiredNumber(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

// GET /api/viewport?minX=..&minY=..&maxX=..&maxY=..&minDegree=..
// Returns the structure tier (nodes + edges, no headword/gloss/source
// text) inside a bounding box, for progressive whole-graph rendering.
// There is no code path that omits the box and falls back to scanning
// the whole table. Binary, not JSON (see ETYM-70): a JSON encoding of
// the full graph's structure runs ~1GB and exceeds V8's string length
// limit, versus ~50MB for the same data as a typed ArrayBuffer.
export const GET: RequestHandler = async ({ url }) => {
  const minX = parseRequiredNumber(url.searchParams.get('minX'));
  const minY = parseRequiredNumber(url.searchParams.get('minY'));
  const maxX = parseRequiredNumber(url.searchParams.get('maxX'));
  const maxY = parseRequiredNumber(url.searchParams.get('maxY'));

  if (minX === null || minY === null || maxX === null || maxY === null) {
    throw error(400, 'minX, minY, maxX, maxY are required numbers');
  }

  const minDegreeParam = url.searchParams.get('minDegree');
  const minDegree = minDegreeParam === null ? 0 : Number(minDegreeParam);
  if (!Number.isFinite(minDegree)) {
    throw error(400, 'minDegree must be a number');
  }

  const tile = await viewportTile({ minX, minY, maxX, maxY }, minDegree);
  return new Response(encodeViewportTile(tile), {
    headers: { 'Content-Type': 'application/octet-stream' },
  });
};
