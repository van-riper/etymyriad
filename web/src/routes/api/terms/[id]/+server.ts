import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { termDetail } from '$lib/server/queries';
import { CACHED_UNTIL_RELOAD } from '$lib/server/edgeCache';
import { parseTermId } from '$lib/shared/validation';

// GET /api/terms/:id
// Fetches one term's attribute-tier detail (senses, source_ref,
// etc.) by id: the lazy per-node fetch triggered by clicking a node.
export const GET: RequestHandler = async ({ params }) => {
  const id = parseTermId(params.id);
  if (id === null) throw error(404, `No term found for id ${params.id}`);
  const term = await termDetail(id);
  if (!term) throw error(404, `No term found for id ${params.id}`);
  return json(term, { headers: { 'cache-control': CACHED_UNTIL_RELOAD } });
};
