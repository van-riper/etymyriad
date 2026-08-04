export function langCodeError(lang: string): string | null {
  return lang.trim() ? null : 'Enter a valid language code.';
}

export function headwordError(headword: string): string | null {
  return headword.trim() ? null : 'Enter a word to look up.';
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}
