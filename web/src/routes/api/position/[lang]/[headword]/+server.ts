import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { lexemePosition } from '$lib/server/queries';

// GET /api/position/:lang/:headword?etym=<etym_key>
// Resolves a word to its precomputed graph position, for centering
// the viewport camera on it. 404s if the lexeme doesn't exist, or
// exists but has no lexeme_layout row yet (not distinguished -- see
// the ETYM-71 design doc). If lang+headword has more than one
// etym_key (a homograph) and no ?etym is given, returns `candidates`
// instead of a position so the caller can let the user pick
// (ETYM-75).
export const GET: RequestHandler = async ({ params, url }) => {
  const etymKey = url.searchParams.get('etym') ?? undefined;
  const result = await lexemePosition(params.lang, params.headword, etymKey);
  if (!result) {
    throw error(404, `No position found for ${params.lang}:${params.headword}`);
  }
  return json(result);
};
