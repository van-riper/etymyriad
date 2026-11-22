import { describe, expect, it } from 'vitest';
import { wiktionaryUrl } from './wiktionary';
import type { Term } from '../shared/types';

const baseTerm: Term = {
  id: 1,
  langCode: 'en',
  langName: 'English',
  headword: 'etymology',
  isReconstructed: false,
  isRedlink: false,
  sourceRef: 'ref',
  senses: [],
};

describe('wiktionaryUrl', () => {
  it('links to the headword page anchored to the language section', () => {
    expect(wiktionaryUrl(baseTerm)).toBe(
      'https://en.wiktionary.org/wiki/etymology#English',
    );
  });

  it('replaces spaces in a multi-word language name with underscores', () => {
    const term = { ...baseTerm, langCode: 'ang', langName: 'Old English' };
    expect(wiktionaryUrl(term)).toBe(
      'https://en.wiktionary.org/wiki/etymology#Old_English',
    );
  });

  it('links to the Reconstruction namespace for a reconstructed form', () => {
    const term = {
      ...baseTerm,
      langCode: 'ine-pro',
      langName: 'Proto-Indo-European',
      headword: '*h2ekweh2',
      isReconstructed: true,
    };
    expect(wiktionaryUrl(term)).toBe(
      'https://en.wiktionary.org/wiki/Reconstruction:Proto-Indo-European/*h2ekweh2',
    );
  });

  it('links an Arabic root to its Appendix page', () => {
    const term = {
      ...baseTerm,
      langCode: 'ar',
      langName: 'Arabic',
      headword: 'ش غ ل',
    };
    const page = encodeURI('Appendix:Arabic_roots/ش_غ_ل');
    expect(wiktionaryUrl(term)).toBe(`https://en.wiktionary.org/wiki/${page}`);
  });

  it('links a multi-word Arabic phrase to its own page', () => {
    const term = {
      ...baseTerm,
      langCode: 'ar',
      langName: 'Arabic',
      headword: 'في سبيل الله',
    };
    const page = encodeURI('في سبيل الله');
    expect(wiktionaryUrl(term)).toBe(
      `https://en.wiktionary.org/wiki/${page}#Arabic`,
    );
  });
});
