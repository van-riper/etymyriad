import type { Lexeme } from '../shared/types';

// Reopening a node's detail card reuses the first /api/lexemes/:id
// response instead of fetching it again.
export async function cachedLexemeDetail(
  cache: Map<string, Lexeme>,
  id: string,
  fetchDetail: (id: string) => Promise<Lexeme | null>,
): Promise<Lexeme | null> {
  const cached = cache.get(id);
  if (cached) return cached;
  const lexeme = await fetchDetail(id);
  if (lexeme) cache.set(id, lexeme);
  return lexeme;
}
