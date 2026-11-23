const UNSUPPORTED_TITLE_ESCAPES: Record<string, string> = {
  lowbar: '_',
  gt: '>',
  lt: '<',
  num: '#',
  tilde: '~',
  period: '.',
  lsqb: '[',
  rsqb: ']',
  vert: '|',
  lcub: '{',
  rcub: '}',
  amp: '&',
};

// Wiktionary stores titles MediaWiki forbids as `name` escapes, e.g.
// `tilde` for ~. Unknown names are left as written.
function decodeEscapes(headword: string): string {
  return headword.replace(
    /`([a-z]+)`/g,
    (token, name: string) => UNSUPPORTED_TITLE_ESCAPES[name] ?? token,
  );
}

// Reconstructed forms use the standard linguistic asterisk convention
// (e.g. *leg-), per is_reconstructed in db/schema.sql.
export function displayHeadword(
  headword: string,
  isReconstructed: boolean,
): string {
  const decoded = decodeEscapes(headword);
  return isReconstructed ? `*${decoded}` : decoded;
}
