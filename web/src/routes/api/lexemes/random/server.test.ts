import { describe, expect, it } from 'vitest';
import { GET } from './+server';

function request(lang?: string): Parameters<typeof GET>[0] {
  const search = lang ? `?lang=${encodeURIComponent(lang)}` : '';
  return {
    url: new URL(`http://localhost/api/lexemes/random${search}`),
  } as Parameters<typeof GET>[0];
}

describe('GET /api/lexemes/random', () => {
  it('returns a real lang_code/headword pair', async () => {
    const response = await GET(request());

    const body = (await response.json()) as {
      langCode: string;
      headword: string;
    };
    expect(typeof body.langCode).toBe('string');
    expect(typeof body.headword).toBe('string');
  });

  it('restricts the pick to the given language', async () => {
    const response = await GET(request('en'));

    const body = (await response.json()) as { langCode: string };
    expect(body.langCode).toBe('en');
  });

  it('404s for a language with no lexemes', async () => {
    await expect(GET(request('zzznotalang'))).rejects.toMatchObject({
      status: 404,
    });
  });
});
