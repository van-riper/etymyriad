import { describe, expect, it } from 'vitest';
import { langCodeError } from './validation';

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
