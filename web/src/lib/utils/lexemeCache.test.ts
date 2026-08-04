import { describe, expect, it, vi } from 'vitest';
import { cachedLexemeDetail } from './lexemeCache';
import type { Lexeme } from '../types';

const lexeme: Lexeme = {
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

describe('cachedLexemeDetail', () => {
  it('fetches once and reuses the cached value on a second call', async () => {
    const cache = new Map<string, Lexeme>();
    const fetchDetail = vi.fn().mockResolvedValue(lexeme);

    const first = await cachedLexemeDetail(cache, 'l1', fetchDetail);
    const second = await cachedLexemeDetail(cache, 'l1', fetchDetail);

    expect(first).toBe(lexeme);
    expect(second).toBe(lexeme);
    expect(fetchDetail).toHaveBeenCalledTimes(1);
  });

  it('does not cache a null result', async () => {
    const cache = new Map<string, Lexeme>();
    const fetchDetail = vi.fn().mockResolvedValue(null);

    await cachedLexemeDetail(cache, 'missing', fetchDetail);
    await cachedLexemeDetail(cache, 'missing', fetchDetail);

    expect(fetchDetail).toHaveBeenCalledTimes(2);
  });
});
