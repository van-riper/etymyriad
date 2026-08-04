import { resolve } from '$app/paths';

// resolve() substitutes path params raw, with no encoding, so an
// embedded '/' (a real headword, e.g. "and/or") would otherwise split
// into extra path segments instead of round-tripping through params.headword.
export function treeUrl(
  lang: string,
  headword: string,
  etym?: string,
): string {
  const path = resolve('/tree/[lang]/[headword]', {
    lang: encodeURIComponent(lang),
    headword: encodeURIComponent(headword),
  });
  return etym ? `${path}?etym=${encodeURIComponent(etym)}` : path;
}
