export function langCodeError(lang: string): string | null {
  return lang.trim() ? null : 'Enter a valid language code.';
}

export function headwordError(headword: string): string | null {
  return headword.trim() ? null : 'Enter a word to look up.';
}

const TERM_ID_RE = /^[1-9]\d{0,9}$/;
const MAX_TERM_ID = 2_147_483_647;
const SECTION_RE = /^(0|[1-9]\d{0,4})$/;
const MAX_SECTION = 32_767;

export function parseTermId(value: string): number | null {
  if (!TERM_ID_RE.test(value)) return null;
  const id = Number(value);
  return id <= MAX_TERM_ID ? id : null;
}

export function parseSection(value: string | null): number | null {
  if (value === null) return 0;
  if (!SECTION_RE.test(value)) return null;
  const section = Number(value);
  return section <= MAX_SECTION ? section : null;
}
