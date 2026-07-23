import type { Lexeme } from './types';

// Reconstructed forms live under Wiktionary's Reconstruction: namespace
// (e.g. Reconstruction:Proto-Indo-European/...), not the main namespace,
// so they need a different path shape rather than just an anchor.
export function wiktionaryUrl(lexeme: Lexeme): string {
  const langAnchor = lexeme.langName.replace(/ /g, '_');
  if (lexeme.isReconstructed) {
    const path = `Reconstruction:${langAnchor}/${lexeme.headword}`;
    return `https://en.wiktionary.org/wiki/${encodeURI(path)}`;
  }
  const page = encodeURI(lexeme.headword);
  return `https://en.wiktionary.org/wiki/${page}#${encodeURI(langAnchor)}`;
}
