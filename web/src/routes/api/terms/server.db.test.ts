import { describe, expect, it } from 'vitest';
import { GET } from './+server';

function request(params: Record<string, string>): Parameters<typeof GET>[0] {
  const search = new URLSearchParams(params).toString();
  return {
    url: new URL(`http://localhost/api/terms?${search}`),
  } as Parameters<typeof GET>[0];
}

describe('GET /api/terms', () => {
  it('resolves a unique headword to a single-element array', async () => {
    const response = await GET(request({ lang: 'en', headword: 'etymology' }));

    const body = (await response.json()) as Array<{ id: number }>;
    expect(body).toHaveLength(1);
    expect(typeof body[0].id).toBe('number');
  });

  it('returns one summary per homograph when ambiguous', async () => {
    const response = await GET(request({ lang: 'en', headword: 'bank' }));

    const body = (await response.json()) as Array<{
      id: number;
      section: number;
    }>;
    expect(body.length).toBeGreaterThan(1);
  });

  it('narrows to one homograph when section is given', async () => {
    const ambiguous = await GET(request({ lang: 'en', headword: 'bank' }));
    const candidates = (await ambiguous.json()) as Array<{
      id: number;
      section: number;
    }>;

    const response = await GET(
      request({
        lang: 'en',
        headword: 'bank',
        section: String(candidates[0].section),
      }),
    );
    const body = (await response.json()) as Array<{ id: number }>;
    expect(body).toEqual([candidates[0]]);
  });

  it('returns an empty array for a headword that does not exist', async () => {
    const response = await GET(
      request({ lang: 'en', headword: 'zzznotaword' }),
    );

    const body = (await response.json()) as unknown[];
    expect(body).toEqual([]);
  });

  it('400s when lang is missing', async () => {
    await expect(GET(request({ headword: 'etymology' }))).rejects.toMatchObject(
      {
        status: 400,
        body: { message: expect.any(String) },
      },
    );
  });

  it('400s when headword is missing', async () => {
    await expect(GET(request({ lang: 'en' }))).rejects.toMatchObject({
      status: 400,
      body: { message: expect.any(String) },
    });
  });

  it('rejects a malformed section', async () => {
    const url = new URL('http://x/api/terms?lang=en&headword=a&section=two');
    await expect(GET({ url } as never)).rejects.toMatchObject({ status: 400 });
  });

  it('lets the edge cache the lookup until the next reload', async () => {
    const response = await GET(request({ lang: 'en', headword: 'etymology' }));

    expect(response.headers.get('cache-control')).toBe(
      'public, s-maxage=86400',
    );
  });
});
