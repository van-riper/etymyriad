import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import Page from './+page.svelte';
import type { Term, TermSummary, TreeSlice } from '$lib/shared/types';

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$app/state', () => ({
  page: { params: { lang: 'en', headword: 'etymology' } },
  navigating: { to: null },
}));

const slice: TreeSlice = {
  focusId: 1,
  nodes: [
    {
      id: 1,
      langCode: 'en',
      headword: 'etymology',
      isReconstructed: false,
      isRedlink: false,
      depth: 0,
    },
    {
      id: 11,
      langCode: 'la',
      headword: 'etymologia',
      isReconstructed: false,
      isRedlink: false,
      depth: -1,
    },
    {
      id: 12,
      langCode: 'la',
      headword: 'filius',
      isReconstructed: false,
      isRedlink: false,
      depth: -1,
    },
  ],
  edges: [],
};

const focusDetail: Term = {
  id: 1,
  langCode: 'en',
  langName: 'English',
  headword: 'etymology',
  isReconstructed: false,
  isRedlink: false,
  sourceRef: 'ref',
  senses: [],
};

const candidates: TermSummary[] = [
  { id: 5, section: 1, partOfSpeech: 'noun', gloss: 'first sense' },
  { id: 5, section: 2, partOfSpeech: 'verb', gloss: 'second sense' },
];

beforeEach(() => {
  goto.mockClear();
  vi.unstubAllGlobals();
});

describe('/tree page', () => {
  it('renders the tree for a resolved word', () => {
    const { getByText } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    expect(getByText('etymologia (la)')).toBeInTheDocument();
  });

  it('navigates to a double-clicked non-focus node', async () => {
    const { getByText } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    await fireEvent.dblClick(getByText('etymologia (la)').closest('.node')!);

    expect(goto).toHaveBeenCalledWith('/tree/la/etymologia');
  });

  it('does not navigate when double-clicking the focus node', async () => {
    const { getByText } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    await fireEvent.dblClick(getByText('etymology (en)').closest('.node')!);

    expect(goto).not.toHaveBeenCalled();
  });

  it("opens a single-clicked non-focus node's detail without navigating", async () => {
    const nodeDetail: Term = {
      id: 11,
      langCode: 'la',
      langName: 'Latin',
      headword: 'etymologia',
      isReconstructed: false,
      isRedlink: false,
      sourceRef: 'ref2',
      senses: [
        { section: 0, partOfSpeech: 'noun', gloss: 'study of word origins' },
      ],
    };
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify(nodeDetail)),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { getByText } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    await fireEvent.click(getByText('etymologia (la)').closest('.node')!);
    await vi.waitFor(() => expect(getByText('Latin')).toBeInTheDocument());

    expect(getByText('study of word origins')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/terms/11');
    expect(goto).not.toHaveBeenCalled();
  });

  it("reverts a clicked node's detail back to the focus word's own on Escape", async () => {
    const nodeDetail: Term = {
      id: 11,
      langCode: 'la',
      langName: 'Latin',
      headword: 'etymologia',
      isReconstructed: false,
      isRedlink: false,
      sourceRef: 'ref2',
      senses: [
        { section: 0, partOfSpeech: 'noun', gloss: 'study of word origins' },
      ],
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(nodeDetail))),
    );

    const { getByText, queryByText } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    await fireEvent.click(getByText('etymologia (la)').closest('.node')!);
    await vi.waitFor(() => expect(getByText('Latin')).toBeInTheDocument());

    await fireEvent.keyDown(window, { key: 'Escape' });

    expect(getByText('English')).toBeInTheDocument();
    expect(queryByText('Latin')).not.toBeInTheDocument();
  });

  it('renders a picker for homograph candidates', () => {
    const { getByText } = render(Page, {
      data: {
        status: 'homograph',
        lang: 'en',
        headword: 'etymology',
        candidates,
      },
    });

    expect(getByText('first sense')).toBeInTheDocument();
    expect(getByText('second sense')).toBeInTheDocument();
  });

  it('navigates with the picked section as the etym query param', async () => {
    const { getByText } = render(Page, {
      data: {
        status: 'homograph',
        lang: 'en',
        headword: 'etymology',
        candidates,
      },
    });

    await fireEvent.click(getByText('second sense'));

    expect(goto).toHaveBeenCalledWith('/tree/en/etymology?etym=2');
  });

  it('navigates to the landing page on Escape from the homograph picker', async () => {
    render(Page, {
      data: {
        status: 'homograph',
        lang: 'en',
        headword: 'etymology',
        candidates,
      },
    });

    await fireEvent.keyDown(window, { key: 'Escape' });

    expect(goto).toHaveBeenCalledWith('/');
  });

  it('renders a not-found message', () => {
    const { getByText } = render(Page, {
      data: { status: 'notfound', lang: 'en', headword: 'xyzzy' },
    });

    expect(getByText(/No matches for "xyzzy" \(en\)/)).toBeInTheDocument();
  });

  it('navigates on search submit with the edited fields', async () => {
    const { getByLabelText, getByRole } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    await fireEvent.input(getByLabelText('Headword'), {
      target: { value: 'father' },
    });
    await fireEvent.click(getByRole('button', { name: 'Search' }));

    expect(goto).toHaveBeenCalledWith('/tree/en/father');
  });

  it('fetches a random word and navigates to it', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ langCode: 'la', headword: 'pater' })),
      ),
    );

    const { getByRole } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    await fireEvent.click(getByRole('button', { name: 'Random' }));
    await vi.waitFor(() => expect(goto).toHaveBeenCalled());

    expect(goto).toHaveBeenCalledWith('/tree/la/pater');
  });

  it('ignores repeat Random clicks while a fetch is in flight', async () => {
    let resolveFetch!: (res: Response) => void;
    const fetchMock = vi.fn<(url: string) => Promise<Response>>(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const { getByRole } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    const randomButton = getByRole('button', { name: 'Random' });
    await fireEvent.click(randomButton);
    expect(randomButton).toBeDisabled();
    await fireEvent.click(randomButton);
    await fireEvent.click(randomButton);

    resolveFetch(
      new Response(JSON.stringify({ langCode: 'la', headword: 'pater' })),
    );
    await vi.waitFor(() => expect(goto).toHaveBeenCalled());

    const randomCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).startsWith('/api/terms/random'),
    );
    expect(randomCalls).toHaveLength(1);
    expect(goto).toHaveBeenCalledTimes(1);
  });

  it('keeps the last-clicked node detail when an earlier fetch resolves later', async () => {
    const detailA: Term = {
      id: 11,
      langCode: 'la',
      langName: 'Latin',
      headword: 'etymologia',
      isReconstructed: false,
      isRedlink: false,
      sourceRef: 'refA',
      senses: [{ section: 0, partOfSpeech: 'noun', gloss: 'A detail' }],
    };
    const detailB: Term = {
      id: 12,
      langCode: 'la',
      langName: 'Latin',
      headword: 'filius',
      isReconstructed: false,
      isRedlink: false,
      sourceRef: 'refB',
      senses: [{ section: 0, partOfSpeech: 'noun', gloss: 'B detail' }],
    };

    let resolveA!: (res: Response) => void;
    const fetchMock = vi.fn<(url: string) => Promise<Response>>((url) => {
      if (url === '/api/terms/11') {
        return new Promise((resolve) => {
          resolveA = resolve;
        });
      }
      if (url === '/api/terms/12') {
        return Promise.resolve(new Response(JSON.stringify(detailB)));
      }
      return Promise.resolve(new Response(JSON.stringify([])));
    });
    vi.stubGlobal('fetch', fetchMock);

    const { getByText } = render(Page, {
      data: {
        status: 'tree',
        lang: 'en',
        headword: 'etymology',
        slice,
        focusDetail,
      },
    });

    await fireEvent.click(getByText('etymologia (la)').closest('.node')!);
    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/terms/11'),
    );

    await fireEvent.click(getByText('filius (la)').closest('.node')!);
    await vi.waitFor(() => expect(getByText('B detail')).toBeInTheDocument());

    resolveA(new Response(JSON.stringify(detailA)));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(getByText('B detail')).toBeInTheDocument();
  });
});
