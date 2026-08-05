import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { fetchWiktionaryPage } from '$lib/server/wiktionaryProxy';

// GET /api/wiktionary?title=...
// The one server route through which every live Wiktionary lookup
// flows (ETYM-138) -- no component or route calls en.wiktionary.org
// directly.
export const GET: RequestHandler = async ({ url }) => {
  const title = url.searchParams.get('title');
  if (!title) {
    throw error(400, 'title query parameter is required');
  }
  const page = await fetchWiktionaryPage(title);
  return json(page);
};
