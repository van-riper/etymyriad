import type { Language } from '../types';

// Ranks languages against a typed query for the language typeahead:
// exact code match, then prefix code match, then a name substring
// match. An empty query surfaces nothing -- the dropdown only opens
// once the user has typed something to narrow ~2k rows.
export function rankLanguages(
  query: string,
  languages: Language[],
): Language[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];

  const exact: Language[] = [];
  const prefix: Language[] = [];
  const nameMatch: Language[] = [];

  for (const lang of languages) {
    const code = lang.code.toLowerCase();
    if (code === q) {
      exact.push(lang);
    } else if (code.startsWith(q)) {
      prefix.push(lang);
    } else if (lang.name.toLowerCase().includes(q)) {
      nameMatch.push(lang);
    }
  }

  return [...exact, ...prefix, ...nameMatch];
}
