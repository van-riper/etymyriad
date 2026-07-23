export function langCodeError(lang: string): string | null {
  return lang.trim() ? null : 'Enter a valid language code.';
}
