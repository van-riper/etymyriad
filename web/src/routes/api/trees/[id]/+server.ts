import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { treeSlice } from '$lib/server/queries';
import { parseSection, parseTermId } from '$lib/shared/validation';

// GET /api/trees/:id?section=
// Bounded bidirectional ancestor/descendant slice around a focus
// term, for /tree's genealogy view. section narrows the focus's
// first ancestor hop to one etymology.
export const GET: RequestHandler = async ({ params, url }) => {
  const id = parseTermId(params.id);
  if (id === null) throw error(404, `No term found for id ${params.id}`);
  const section = parseSection(url.searchParams.get('section'));
  if (section === null) throw error(400, 'section must be 0 to 32767');
  const tree = await treeSlice(id, section);
  if (!tree) throw error(404, `No term found for id ${params.id}`);
  return json(tree);
};
