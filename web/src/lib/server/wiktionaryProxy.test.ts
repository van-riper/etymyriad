import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchWiktionaryPage } from './wiktionaryProxy';

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

describe('fetchWiktionaryPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends a descriptive User-Agent, per Wikimedia API etiquette', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ parse: { title: 'etymology', wikitext: { '*': 'x' } } }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await fetchWiktionaryPage('etymology');

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((options.headers as Record<string, string>)['User-Agent']).toMatch(
      /etymyriad/i,
    );
  });

  it('returns the wikitext for a page that exists', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          parse: { title: 'bank', wikitext: { '*': 'wikitext body' } },
        }),
      ),
    );

    const page = await fetchWiktionaryPage('bank');
    expect(page).toEqual({ title: 'bank', wikitext: 'wikitext body' });
  });

  it('returns null for a page that does not exist', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ error: { code: 'missingtitle' } })),
    );

    const page = await fetchWiktionaryPage('doesnotexist12345');
    expect(page).toBeNull();
  });

  it('skips the network call for a repeated lookup within the cache window', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ parse: { title: 'ash', wikitext: { '*': 'x' } } }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await fetchWiktionaryPage('ash');
    await fetchWiktionaryPage('ash');

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('throws when the upstream request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('', { status: 503 })),
    );

    await expect(fetchWiktionaryPage('unreliable')).rejects.toThrow();
  });
});
