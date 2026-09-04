import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { lexemesByHeadword } from '$lib/server/queries';
import { headwordError, langCodeError } from '$lib/shared/validation';

// GET /api/lexemes?lang=&headword=&etym=
// Resolves a (lang, headword) pair to its lexeme(s). A unique match
// is a single-element array; a homograph returns one summary per
// candidate for a disambiguation picker. No match is an
// empty array: the collection itself always exists, so an empty
// result set isn't a 404.
export const GET: RequestHandler = async ({ url }) => {
  const lang = url.searchParams.get('lang') ?? '';
  const headword = url.searchParams.get('headword') ?? '';
  const etym = url.searchParams.get('etym') ?? undefined;

  const langError = langCodeError(lang);
  if (langError) throw error(400, langError);
  const wordError = headwordError(headword);
  if (wordError) throw error(400, wordError);

  const matches = await lexemesByHeadword(lang, headword, etym);
  return json(matches);
};
