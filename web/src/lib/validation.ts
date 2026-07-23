export function langCodeError(lang: string): string | null {
  return lang.trim() ? null : 'Enter a valid language code.';
}

export function headwordError(headword: string): string | null {
  return headword.trim() ? null : 'Enter a word to look up.';
}
