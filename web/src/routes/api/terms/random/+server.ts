import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { randomTerm } from '$lib/server/queries';

// GET /api/terms/random?lang=en
// Returns a random term's lang/headword, for the "random word" button.
// Restricted to ?lang when given, otherwise any language.
export const GET: RequestHandler = async ({ url }) => {
  const lang = url.searchParams.get('lang') || undefined;
  const pick = await randomTerm(lang);
  if (!pick) {
    throw error(404, `No terms found${lang ? ` for language ${lang}` : ''}`);
  }
  return json(pick);
};
