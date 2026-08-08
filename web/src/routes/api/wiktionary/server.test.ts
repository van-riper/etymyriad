import { describe, expect, it, vi } from 'vitest';

vi.mock('$lib/server/wiktionaryProxy', () => ({
  fetchWiktionaryPage: vi.fn(),
}));

import { GET } from './+server';
import { fetchWiktionaryPage } from '$lib/server/wiktionaryProxy';

describe('GET /api/wiktionary', () => {
  it('400s when the title query parameter is missing', async () => {
    await expect(
      GET({
        url: new URL('http://localhost/api/wiktionary'),
      } as Parameters<typeof GET>[0]),
    ).rejects.toMatchObject({
      status: 400,
      body: { message: expect.any(String) },
    });
  });

  it('returns the page for a title that exists', async () => {
    vi.mocked(fetchWiktionaryPage).mockResolvedValue({
      title: 'etymology',
      wikitext: 'text',
    });

    const response = await GET({
      url: new URL('http://localhost/api/wiktionary?title=etymology'),
    } as Parameters<typeof GET>[0]);

    expect(fetchWiktionaryPage).toHaveBeenCalledWith('etymology');
    expect(await response.json()).toEqual({
      title: 'etymology',
      wikitext: 'text',
    });
  });

  it('returns null for a title that does not exist', async () => {
    vi.mocked(fetchWiktionaryPage).mockResolvedValue(null);

    const response = await GET({
      url: new URL('http://localhost/api/wiktionary?title=doesnotexist'),
    } as Parameters<typeof GET>[0]);

    expect(await response.json()).toBeNull();
  });
});
