import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { termsByHeadword } from '$lib/server/queries';
import { CACHED_UNTIL_RELOAD } from '$lib/server/edgeCache';
import {
  headwordError,
  langCodeError,
  parseSection,
} from '$lib/shared/validation';

// GET /api/terms?lang=&headword=&section=
// Resolves a (lang, headword) pair to one summary per section. A
// unique match is a single-element array; a homograph returns one
// summary per candidate for a disambiguation picker. No match is an
// empty array: the collection itself always exists, so an empty
// result set isn't a 404.
export const GET: RequestHandler = async ({ url }) => {
  const lang = url.searchParams.get('lang') ?? '';
  const headword = url.searchParams.get('headword') ?? '';
  const sectionParam = url.searchParams.get('section');

  const langError = langCodeError(lang);
  if (langError) throw error(400, langError);
  const wordError = headwordError(headword);
  if (wordError) throw error(400, wordError);
  const section =
    sectionParam === null ? undefined : parseSection(sectionParam);
  if (section === null) throw error(400, 'section must be 0 to 32767');

  const matches = await termsByHeadword(lang, headword, section);
  return json(matches, { headers: { 'cache-control': CACHED_UNTIL_RELOAD } });
};
