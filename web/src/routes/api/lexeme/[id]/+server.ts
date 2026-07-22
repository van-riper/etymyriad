import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { lexemeDetail } from '$lib/server/queries';

// GET /api/lexeme/:id
// Fetches one lexeme's attribute-tier detail (senses, source_ref,
// etc.) by id -- the lazy per-node fetch triggered by hovering or
// clicking a node in the viewport-tile structure tier.
export const GET: RequestHandler = async ({ params }) => {
  const lexeme = await lexemeDetail(params.id);
  if (!lexeme) {
    throw error(404, `No lexeme found for id ${params.id}`);
  }
  return json(lexeme);
};
