import { describe, expect, it } from 'vitest';
import {
  headwordError,
  langCodeError,
  parseSection,
  parseTermId,
} from './validation';

describe('langCodeError', () => {
  it('flags an empty language code', () => {
    expect(langCodeError('')).toBe('Enter a valid language code.');
  });

  it('flags a whitespace-only language code', () => {
    expect(langCodeError('   ')).toBe('Enter a valid language code.');
  });

  it('accepts a real language code', () => {
    expect(langCodeError('en')).toBeNull();
  });
});

describe('headwordError', () => {
  it('flags an empty headword', () => {
    expect(headwordError('')).toBe('Enter a word to look up.');
  });

  it('flags a whitespace-only headword', () => {
    expect(headwordError('   ')).toBe('Enter a word to look up.');
  });

  it('accepts a real headword', () => {
    expect(headwordError('etymology')).toBeNull();
  });
});

describe('parseTermId', () => {
  it('accepts a positive int4', () => {
    expect(parseTermId('42')).toBe(42);
    expect(parseTermId('2147483647')).toBe(2147483647);
  });

  it('rejects anything else', () => {
    for (const bad of ['0', '-1', '1.5', '2147483648', 'abc', '', '01']) {
      expect(parseTermId(bad)).toBeNull();
    }
  });
});

describe('parseSection', () => {
  it('defaults a missing section to 0', () => {
    expect(parseSection(null)).toBe(0);
  });

  it('accepts 0 through 32767', () => {
    expect(parseSection('0')).toBe(0);
    expect(parseSection('32767')).toBe(32767);
  });

  it('rejects anything else', () => {
    for (const bad of ['-1', '32768', 'two', '', '1e3']) {
      expect(parseSection(bad)).toBeNull();
    }
  });
});
