import { describe, expect, it, vi } from 'vitest';
import { fetchDefaultTreeSlice } from './snapshotDefaultTree';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe('fetchDefaultTreeSlice', () => {
  it('resolves the term, then fetches its section 0 tree', async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes('/api/terms?')
        ? jsonResponse([{ id: 7 }])
        : jsonResponse({ focusId: 7 }),
    );

    const slice = await fetchDefaultTreeSlice(
      'http://x',
      'en',
      'etymology',
      fetchMock,
    );

    expect(slice).toEqual({ focusId: 7 });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://x/api/terms?lang=en&headword=etymology&section=0',
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://x/api/trees/7?section=0',
    );
  });

  it('throws when the term is missing', async () => {
    const fetchMock = vi.fn(async () => jsonResponse([]));

    await expect(
      fetchDefaultTreeSlice('http://x', 'en', 'nope', fetchMock),
    ).rejects.toThrow('No term found for en:nope');
  });

  it('throws on a failed response', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({}, 500));

    await expect(
      fetchDefaultTreeSlice('http://x', 'en', 'etymology', fetchMock),
    ).rejects.toThrow('500');
  });
});
