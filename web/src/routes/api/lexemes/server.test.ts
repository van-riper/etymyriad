import { describe, expect, it } from 'vitest';
import { GET } from './+server';

function request(params: Record<string, string>): Parameters<typeof GET>[0] {
  const search = new URLSearchParams(params).toString();
  return {
    url: new URL(`http://localhost/api/lexemes?${search}`),
  } as Parameters<typeof GET>[0];
}

describe('GET /api/lexemes', () => {
  it('resolves a unique headword to a single-element array', async () => {
    const response = await GET(request({ lang: 'en', headword: 'etymology' }));

    const body = (await response.json()) as Array<{ id: string }>;
    expect(body).toHaveLength(1);
    expect(typeof body[0].id).toBe('string');
  });

  it('returns one summary per homograph when ambiguous', async () => {
    const response = await GET(request({ lang: 'en', headword: 'bank' }));

    const body = (await response.json()) as Array<{
      id: string;
      etymKey: string;
    }>;
    expect(body.length).toBeGreaterThan(1);
  });

  it('narrows to one homograph when etym is given', async () => {
    const ambiguous = await GET(request({ lang: 'en', headword: 'bank' }));
    const candidates = (await ambiguous.json()) as Array<{
      id: string;
      etymKey: string;
    }>;

    const response = await GET(
      request({ lang: 'en', headword: 'bank', etym: candidates[0].etymKey }),
    );
    const body = (await response.json()) as Array<{ id: string }>;
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
    await expect(
      GET(request({ headword: 'etymology' })),
    ).rejects.toMatchObject({ status: 400 });
  });

  it('400s when headword is missing', async () => {
    await expect(GET(request({ lang: 'en' }))).rejects.toMatchObject({
      status: 400,
    });
  });
});
