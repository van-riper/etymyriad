import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { randomLexeme } from '$lib/server/queries';

// GET /api/lexemes/random?lang=en
// Returns a random lexeme's lang/headword, for the "random word" button.
// Restricted to ?lang when given, otherwise any language.
export const GET: RequestHandler = async ({ url }) => {
  const lang = url.searchParams.get('lang') || undefined;
  const pick = await randomLexeme(lang);
  if (!pick) {
    throw error(404, `No lexemes found${lang ? ` for language ${lang}` : ''}`);
  }
  return json(pick);
};
