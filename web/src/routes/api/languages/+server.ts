import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { languageList } from '$lib/server/queries';

// GET /api/languages
// Every language's {code, name}, for the client-side typeahead
// (ETYM-85). The table only changes via an ETL run, not per-request,
// so the response is cacheable indefinitely.
export const GET: RequestHandler = async () => {
  const languages = await languageList();
  return json(languages, {
    headers: { 'cache-control': 'public, max-age=86400' },
  });
};
