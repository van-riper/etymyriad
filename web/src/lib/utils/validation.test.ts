import { describe, expect, it } from 'vitest';
import { headwordError, isUuid, langCodeError } from './validation';

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

describe('isUuid', () => {
  it('accepts a well-formed UUID', () => {
    expect(isUuid('123e4567-e89b-12d3-a456-426614174000')).toBe(true);
  });

  it('accepts uppercase hex digits', () => {
    expect(isUuid('123E4567-E89B-12D3-A456-426614174000')).toBe(true);
  });

  it('rejects a non-UUID string', () => {
    expect(isUuid('not-a-uuid')).toBe(false);
  });

  it('rejects an id missing a segment', () => {
    expect(isUuid('123e4567-e89b-12d3-a456')).toBe(false);
  });
});
