import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { termDetail, treeExpand } from '$lib/server/queries';
import { parseSection, parseTermId } from '$lib/shared/validation';

// GET /api/trees/:id/expand?dir=ancestor|descendant&depth=<signed
// int>&exclude=<comma-separated term ids>&section=
//
// Fetches the next batch of :id's children beyond what the caller
// already has, in one direction, for the "+N more" affordance:
// scoped to exactly what it reveals, not a re-slice of an
// already-fetched oversized payload. depth is :id's own
// already-known signed depth from the original focus. section
// narrows the first hop, for expanding the focus itself.
export const GET: RequestHandler = async ({ params, url }) => {
  const id = parseTermId(params.id);
  if (id === null) throw error(404, `No term found for id ${params.id}`);

  const dir = url.searchParams.get('dir');
  if (dir !== 'ancestor' && dir !== 'descendant') {
    throw error(400, `dir must be "ancestor" or "descendant", got "${dir}"`);
  }

  const depthParam = url.searchParams.get('depth');
  const depth = Number(depthParam);
  if (depthParam === null || !Number.isInteger(depth)) {
    throw error(400, `depth must be an integer, got "${depthParam}"`);
  }

  const parsed = (url.searchParams.get('exclude') ?? '')
    .split(',')
    .filter((part) => part.length > 0)
    .map(parseTermId);
  const exclude = parsed.filter((part) => part !== null);
  if (exclude.length !== parsed.length) {
    throw error(400, 'exclude must be a comma-separated list of term ids');
  }

  const section = parseSection(url.searchParams.get('section'));
  if (section === null) throw error(400, 'section must be 0 to 32767');

  if (!(await termDetail(id))) {
    throw error(404, `No term found for id ${params.id}`);
  }
  const expansion = await treeExpand(id, dir, depth, exclude, section);
  return json(expansion);
};
