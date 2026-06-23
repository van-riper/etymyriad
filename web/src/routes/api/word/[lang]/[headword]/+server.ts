import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { egoNetwork } from '$lib/server/queries';

// GET /api/word/:lang/:headword?depth=2
// Returns the ego-network (focused graph slice) for one word.
export const GET: RequestHandler = async ({ params, url }) => {
  const depth = Number(url.searchParams.get('depth') ?? '2');
  const safeDepth = Number.isFinite(depth)
    ? Math.min(Math.max(depth, 1), 4)
    : 2;

  const network = await egoNetwork(params.lang, params.headword, safeDepth);
  if (!network) {
    throw error(404, `No lexeme found for ${params.lang}:${params.headword}`);
  }

  return json(network);
};
