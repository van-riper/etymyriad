import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { lexemeDetail, treeExpand } from '$lib/server/queries';
import { isUuid } from '$lib/utils/validation';

// GET /api/trees/:id/expand?dir=ancestor|descendant&depth=<signed
// int>&exclude=<comma-separated uuids>
//
// Fetches the next batch of :id's children beyond what the caller
// already has, in one direction, for the "+N more" affordance
// (ETYM-144) -- scoped to exactly what it reveals, not a re-slice of
// an already-fetched oversized payload. depth is :id's own
// already-known signed depth from the original focus.
export const GET: RequestHandler = async ({ params, url }) => {
  if (!isUuid(params.id)) {
    throw error(404, `No lexeme found for id ${params.id}`);
  }
  if (!(await lexemeDetail(params.id))) {
    throw error(404, `No lexeme found for id ${params.id}`);
  }

  const dir = url.searchParams.get('dir');
  if (dir !== 'ancestor' && dir !== 'descendant') {
    throw error(400, `dir must be "ancestor" or "descendant", got "${dir}"`);
  }

  const depthParam = url.searchParams.get('depth');
  const depth = Number(depthParam);
  if (depthParam === null || !Number.isInteger(depth)) {
    throw error(400, `depth must be an integer, got "${depthParam}"`);
  }

  const exclude = (url.searchParams.get('exclude') ?? '')
    .split(',')
    .filter((id) => id.length > 0);
  if (!exclude.every(isUuid)) {
    throw error(400, 'exclude must be a comma-separated list of UUIDs');
  }

  const expansion = await treeExpand(params.id, dir, depth, exclude);
  return json(expansion);
};
