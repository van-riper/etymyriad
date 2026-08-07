import { describe, expect, it, vi } from 'vitest';
import { load } from './+page';
import type { LexemeSummary, TreeSlice, Lexeme } from '$lib/types';

const summary = (etymKey: string): LexemeSummary => ({
  id: `id-${etymKey}`,
  etymKey,
  pos: 'noun',
  gloss: 'a gloss',
});

const slice: TreeSlice = { focusId: 'id-a', nodes: [], edges: [] };
const lexeme = { id: 'id-a' } as unknown as Lexeme;

function loadEvent(matches: LexemeSummary[], etym?: string) {
  const fetch = vi.fn(async (url: string) => {
    if (url.startsWith('/api/lexemes?')) {
      return new Response(JSON.stringify(matches));
    }
    if (url.startsWith('/api/trees/')) {
      return new Response(JSON.stringify(slice));
    }
    if (url.startsWith('/api/lexemes/')) {
      return new Response(JSON.stringify(lexeme));
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
  const search = new URLSearchParams(etym ? { etym } : {});
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
    const event = loadEvent([summary('a')]);
    const data = await load(event as never);

    expect(data).toEqual({
      status: 'tree',
      lang: 'en',
      headword: 'etymology',
      slice,
      focusDetail: lexeme,
    });
    expect(event.fetch).toHaveBeenCalledWith('/api/trees/id-a');
    expect(event.fetch).toHaveBeenCalledWith('/api/lexemes/id-a');
  });

  it('returns homograph candidates when unresolved and no etym given', async () => {
    const candidates = [summary('a'), summary('b')];
    const data = await load(loadEvent(candidates) as never);

    expect(data).toEqual({
      status: 'homograph',
      lang: 'en',
      headword: 'etymology',
      candidates,
    });
  });

  it('throws when the /api/lexemes response is not ok', async () => {
    const fetch = vi.fn(async (url: string) => {
      if (url.startsWith('/api/lexemes?')) {
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
    const event = loadEvent([summary('a')], 'a');
    const data = await load(event as never);

    expect(data).toEqual({
      status: 'tree',
      lang: 'en',
      headword: 'etymology',
      slice,
      focusDetail: lexeme,
    });
    expect(event.fetch).toHaveBeenCalledWith(
      '/api/lexemes?lang=en&headword=etymology&etym=a',
    );
  });
});
