import { describe, expect, it, vi } from 'vitest';
import { load } from './+page';
import type { TermSummary, TreeSlice, Term } from '$lib/shared/types';

const summary = (id: number, section: number): TermSummary => ({
  id,
  section,
  partOfSpeech: 'noun',
  gloss: 'a gloss',
});

const slice: TreeSlice = { focusId: 1, nodes: [], edges: [] };
const term = { id: 1 } as unknown as Term;

function loadEvent(matches: TermSummary[], etym?: string) {
  const fetch = vi.fn(async (url: string) => {
    if (url.startsWith('/api/terms?')) {
      const section = new URLSearchParams(url.split('?')[1]).get('section');
      return new Response(
        JSON.stringify(
          section === null
            ? matches
            : matches.filter((m) => m.section === Number(section)),
        ),
      );
    }
    if (url.startsWith('/api/trees/')) {
      return new Response(JSON.stringify(slice));
    }
    if (url.startsWith('/api/terms/')) {
      return new Response(JSON.stringify(term));
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
  const search = new URLSearchParams(etym === undefined ? {} : { etym });
  return {
    params: { lang: 'en', headword: 'etymology' },
    url: { searchParams: search } as URL,
    fetch,
  };
}

describe('load', () => {
  it('returns notfound when there are no matches', async () => {
    const data = await load(loadEvent([]) as never);
    expect(data).toEqual({
      status: 'notfound',
      lang: 'en',
      headword: 'etymology',
    });
  });

  it('returns a tree slice and focus detail for a unique match', async () => {
    const event = loadEvent([summary(1, 3)]);
    const data = await load(event as never);

    expect(data).toEqual({
      status: 'tree',
      lang: 'en',
      headword: 'etymology',
      slice,
      focusDetail: term,
    });
    expect(event.fetch).toHaveBeenCalledWith('/api/trees/1?section=3');
    expect(event.fetch).toHaveBeenCalledWith('/api/terms/1');
  });

  it('returns homograph candidates when unresolved and no etym given', async () => {
    const candidates = [summary(1, 1), summary(1, 2)];
    const event = loadEvent(candidates);
    const data = await load(event as never);

    expect(data).toEqual({
      status: 'homograph',
      lang: 'en',
      headword: 'etymology',
      candidates,
    });
    expect(event.fetch).toHaveBeenCalledWith(
      '/api/terms?lang=en&headword=etymology',
    );
  });

  it('throws when the /api/terms response is not ok', async () => {
    const fetch = vi.fn(async (url: string) => {
      if (url.startsWith('/api/terms?')) {
        return new Response(
          JSON.stringify({ message: 'Enter a valid language code.' }),
          { status: 400 },
        );
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const event = {
      params: { lang: '', headword: 'etymology' },
      url: { searchParams: new URLSearchParams() } as URL,
      fetch,
    };

    await expect(load(event as never)).rejects.toMatchObject({
      status: 400,
      body: { message: 'Enter a valid language code.' },
    });
  });

  it('resolves to a single tree when etym narrows a homograph', async () => {
    const event = loadEvent([summary(1, 2)], '2');
    const data = await load(event as never);

    expect(data).toMatchObject({ status: 'tree' });
    expect(event.fetch).toHaveBeenCalledWith(
      '/api/terms?lang=en&headword=etymology&section=2',
    );
  });

  it('treats an empty etym as absent', async () => {
    const candidates = [summary(1, 1), summary(1, 2)];
    const event = loadEvent(candidates, '');
    const data = await load(event as never);

    expect(data).toMatchObject({ status: 'homograph', candidates });
    expect(event.fetch).toHaveBeenCalledWith(
      '/api/terms?lang=en&headword=etymology',
    );
  });

  it('treats a formof etym as absent', async () => {
    const event = loadEvent([summary(1, 0)], 'formof:noun');
    const data = await load(event as never);

    expect(data).toMatchObject({ status: 'tree' });
    expect(event.fetch).toHaveBeenCalledWith(
      '/api/terms?lang=en&headword=etymology',
    );
  });

  it('falls back to every section when etym names a missing one', async () => {
    const candidates = [1, 2, 3, 4].map((n) => summary(1, n));
    const event = loadEvent(candidates, '7');
    const data = await load(event as never);

    expect(data).toMatchObject({ status: 'homograph', candidates });
    expect(event.fetch).toHaveBeenCalledWith(
      '/api/terms?lang=en&headword=etymology&section=7',
    );
    expect(event.fetch).toHaveBeenCalledWith(
      '/api/terms?lang=en&headword=etymology',
    );
  });
});
