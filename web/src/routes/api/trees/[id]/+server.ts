import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { treeSlice } from '$lib/server/queries';
import { isUuid } from '$lib/utils/validation';

// GET /api/trees/:id
// Bounded bidirectional ancestor/descendant slice around a focus
// lexeme, for /tree's genealogy view.
export const GET: RequestHandler = async ({ params }) => {
  if (!isUuid(params.id)) {
    throw error(404, `No lexeme found for id ${params.id}`);
  }
  const tree = await treeSlice(params.id);
  if (!tree) {
    throw error(404, `No lexeme found for id ${params.id}`);
  }
  return json(tree);
};
