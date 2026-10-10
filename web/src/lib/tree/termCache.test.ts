import { describe, expect, it, vi } from 'vitest';
import { cachedTermDetail } from './termCache';
import type { Term } from '../shared/types';

const term: Term = {
  id: 1,
  langCode: 'en',
  langName: 'English',
  headword: 'etymology',
  isReconstructed: false,
  isRedlink: false,
  sourceRef: 'ref',
  senses: [],
};

describe('cachedTermDetail', () => {
  it('fetches once and reuses the cached value on a second call', async () => {
    const cache = new Map<number, Term>();
    const fetchDetail = vi.fn().mockResolvedValue(term);

    const first = await cachedTermDetail(cache, 1, fetchDetail);
    const second = await cachedTermDetail(cache, 1, fetchDetail);

    expect(first).toBe(term);
    expect(second).toBe(term);
    expect(fetchDetail).toHaveBeenCalledTimes(1);
  });

  it('does not cache a null result', async () => {
    const cache = new Map<number, Term>();
    const fetchDetail = vi.fn().mockResolvedValue(null);

    await cachedTermDetail(cache, 2, fetchDetail);
    await cachedTermDetail(cache, 2, fetchDetail);

    expect(fetchDetail).toHaveBeenCalledTimes(2);
  });
});
