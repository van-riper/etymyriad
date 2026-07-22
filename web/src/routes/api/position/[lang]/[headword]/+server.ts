import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { lexemePosition } from '$lib/server/queries';

// GET /api/position/:lang/:headword
// Resolves a word to its precomputed graph position, for centering
// the viewport camera on it. 404s if the lexeme doesn't exist, or
// exists but has no lexeme_layout row yet (not distinguished -- see
// the ETYM-71 design doc).
export const GET: RequestHandler = async ({ params }) => {
  const position = await lexemePosition(params.lang, params.headword);
  if (!position) {
    throw error(404, `No position found for ${params.lang}:${params.headword}`);
  }
  return json(position);
};
