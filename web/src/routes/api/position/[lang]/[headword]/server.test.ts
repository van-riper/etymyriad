import { describe, expect, it } from 'vitest';
import { GET } from './+server';

function requestWithEtym(
  lang: string,
  headword: string,
  etym?: string,
): Parameters<typeof GET>[0] {
  const search = etym !== undefined ? `?etym=${encodeURIComponent(etym)}` : '';
  return {
    params: { lang, headword },
    url: new URL(`http://localhost/api/position/${lang}/${headword}${search}`),
  } as Parameters<typeof GET>[0];
}

describe('GET /api/position/:lang/:headword', () => {
  it('returns the position for a real lexeme', async () => {
    const response = await GET(requestWithEtym('en', 'etymology'));

    const body = (await response.json()) as {
      id: string;
      x: number;
      y: number;
    };
    expect(typeof body.id).toBe('string');
    expect(typeof body.x).toBe('number');
    expect(typeof body.y).toBe('number');
  });

  it('404s for a headword that does not exist', async () => {
    await expect(
      GET(requestWithEtym('en', 'zzznotaword')),
    ).rejects.toMatchObject({ status: 404 });
  });

  it('returns candidates for an ambiguous headword', async () => {
    const response = await GET(requestWithEtym('en', 'bank'));

    const body = (await response.json()) as {
      candidates: Array<{ etymKey: string; id: string }>;
    };
    expect(Array.isArray(body.candidates)).toBe(true);
    expect(body.candidates.length).toBeGreaterThan(1);
  });

  it('resolves one homograph when etym is given', async () => {
    const ambiguous = await GET(requestWithEtym('en', 'bank'));
    const { candidates } = (await ambiguous.json()) as {
      candidates: Array<{ etymKey: string; id: string }>;
    };

    const response = await GET(
      requestWithEtym('en', 'bank', candidates[0].etymKey),
    );
    const body = (await response.json()) as { id: string };
    expect(body.id).toBe(candidates[0].id);
  });
});
