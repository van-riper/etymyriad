import { describe, expect, it } from 'vitest';
import { headwordError, langCodeError } from './validation';

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
