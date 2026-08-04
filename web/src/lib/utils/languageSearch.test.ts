import { describe, expect, it } from 'vitest';
import { rankLanguages } from './languageSearch';
import type { Language } from '../types';

const languages: Language[] = [
  { code: 'gem-pro', name: 'Proto-Germanic' },
  { code: 'de', name: 'German' },
  { code: 'en', name: 'English' },
  { code: 'la', name: 'Latin' },
];

describe('rankLanguages', () => {
  it('ranks a prefix code match above name matches', () => {
    const result = rankLanguages('gem', languages);
    expect(result[0].code).toBe('gem-pro');
  });

  it('ranks an exact code match first', () => {
    const result = rankLanguages('de', languages);
    expect(result[0].code).toBe('de');
  });

  it('matches on a language-name substring', () => {
    const result = rankLanguages('german', languages);
    expect(new Set(result.map((l) => l.code))).toEqual(
      new Set(['de', 'gem-pro']),
    );
  });

  it('is case-insensitive', () => {
    const result = rankLanguages('LATIN', languages);
    expect(result[0].code).toBe('la');
  });

  it('returns nothing for an empty query', () => {
    expect(rankLanguages('', languages)).toEqual([]);
  });

  it('returns nothing when nothing matches', () => {
    expect(rankLanguages('xyz', languages)).toEqual([]);
  });
});
