import type { Lexeme } from '../shared/types';

// Shared by hover and click handlers so hovering then clicking the
// same node issues one /api/lexemes/:id request, not two.
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
