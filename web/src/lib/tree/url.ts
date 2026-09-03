import { resolve } from '$app/paths';
import type { ResolvedPathname } from '$app/types';

// resolve() substitutes path params raw, with no encoding, so an
// embedded '/' (a real headword, e.g. "and/or") would otherwise split
// into extra path segments instead of round-tripping through params.headword.
export function treeUrl(
  lang: string,
  headword: string,
  etym?: string,
): ResolvedPathname {
  const path = resolve('/tree/[lang]/[headword]', {
    lang: encodeURIComponent(lang),
    headword: encodeURIComponent(headword),
  });
  // Appending a query string still targets the same resolved route, so
  // the result stays a valid ResolvedPathname despite the cast.
  // An unnumbered entry's etym_key is the empty string, so the param is
  // kept whenever it was passed at all, not just when it's non-empty.
  return (
    etym === undefined ? path : `${path}?etym=${encodeURIComponent(etym)}`
  ) as ResolvedPathname;
}
