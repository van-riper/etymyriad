import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { randomLexeme } from '$lib/server/queries';

// GET /api/random
// Returns a random lexeme's lang/headword, for the "random word" button.
export const GET: RequestHandler = async () => {
  const pick = await randomLexeme();
  if (!pick) {
    throw error(404, 'No lexemes in the database');
  }
  return json(pick);
};
