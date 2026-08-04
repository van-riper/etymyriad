import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { lexemeDetail } from '$lib/server/queries';
import { isUuid } from '$lib/validation';

// GET /api/lexeme/:id
// Fetches one lexeme's attribute-tier detail (senses, source_ref,
// etc.) by id -- the lazy per-node fetch triggered by hovering or
// clicking a node.
export const GET: RequestHandler = async ({ params }) => {
  // A non-UUID id would otherwise reach Postgres and throw an
  // unhandled "invalid input syntax for type uuid" 500.
  if (!isUuid(params.id)) {
    throw error(404, `No lexeme found for id ${params.id}`);
  }
  const lexeme = await lexemeDetail(params.id);
  if (!lexeme) {
    throw error(404, `No lexeme found for id ${params.id}`);
  }
  return json(lexeme);
};
