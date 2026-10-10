import type { Term } from '../shared/types';

// Reconstructed forms live under Wiktionary's Reconstruction: namespace
// (e.g. Reconstruction:Proto-Indo-European/...), not the main namespace,
// so they need a different path shape rather than just an anchor.
export function wiktionaryUrl(term: Term): string {
  const langAnchor = term.langName.replace(/ /g, '_');
  if (term.isReconstructed) {
    const path = `Reconstruction:${langAnchor}/${term.headword}`;
    return `https://en.wiktionary.org/wiki/${encodeURI(path)}`;
  }
  const page = encodeURI(term.headword);
  return `https://en.wiktionary.org/wiki/${page}#${encodeURI(langAnchor)}`;
}
