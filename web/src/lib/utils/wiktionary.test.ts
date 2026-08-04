import { describe, expect, it } from 'vitest';
import { wiktionaryUrl } from './wiktionary';
import type { Lexeme } from '../types';

const baseLexeme: Lexeme = {
  id: 'l1',
  langCode: 'en',
  langName: 'English',
  headword: 'etymology',
  etymologyNumber: null,
  romanization: null,
  isReconstructed: false,
  sourceRef: 'ref',
  senses: [],
};

describe('wiktionaryUrl', () => {
  it('links to the headword page anchored to the language section', () => {
    expect(wiktionaryUrl(baseLexeme)).toBe(
      'https://en.wiktionary.org/wiki/etymology#English',
    );
  });

  it('replaces spaces in a multi-word language name with underscores', () => {
    const lexeme = { ...baseLexeme, langCode: 'ang', langName: 'Old English' };
    expect(wiktionaryUrl(lexeme)).toBe(
      'https://en.wiktionary.org/wiki/etymology#Old_English',
    );
  });

  it('links to the Reconstruction namespace for a reconstructed form', () => {
    const lexeme = {
      ...baseLexeme,
      langCode: 'ine-pro',
      langName: 'Proto-Indo-European',
      headword: '*h2ekweh2',
      isReconstructed: true,
    };
    expect(wiktionaryUrl(lexeme)).toBe(
      'https://en.wiktionary.org/wiki/Reconstruction:Proto-Indo-European/*h2ekweh2',
    );
  });
});
