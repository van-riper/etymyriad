import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import Page from './+page.svelte';
import type { Lexeme, LexemeSummary, TreeSlice } from '$lib/shared/types';

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$app/state', () => ({
  page: { params: { lang: 'en', headword: 'etymology' } },
  navigating: { to: null },
}));

const slice: TreeSlice = {
  focusId: 'f',
  nodes: [
    {
      id: 'f',
      langCode: 'en',
      headword: 'etymology',
      isReconstructed: false,
      depth: 0,
    },
    {
      id: 'a1',
      langCode: 'la',
      headword: 'etymologia',
      isReconstructed: false,
      depth: -1,
    },
  ],
  edges: [],
};

const focusDetail: Lexeme = {
  id: 'f',
  langCode: 'en',
  langName: 'English',
  headword: 'etymology',
  etymologyNumber: null,
  romanization: null,
  isReconstructed: false,
  sourceRef: 'ref',
  senses: [],
};

const candidates: LexemeSummary[] = [
  { id: 'c1', etymKey: 'a', pos: 'noun', gloss: 'first sense' },
  { id: 'c2', etymKey: 'b', pos: 'verb', gloss: 'second sense' },
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
    const nodeDetail: Lexeme = {
      id: 'a1',
      langCode: 'la',
      langName: 'Latin',
      headword: 'etymologia',
      etymologyNumber: null,
      romanization: null,
      isReconstructed: false,
      sourceRef: 'ref2',
      senses: [
        { pos: 'noun', gloss: 'study of word origins', sourceRef: 'ref2' },
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
    expect(fetchMock).toHaveBeenCalledWith('/api/lexemes/a1');
    expect(goto).not.toHaveBeenCalled();
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

  it('navigates with the etym query param when a candidate is picked', async () => {
    const { getByText } = render(Page, {
      data: {
        status: 'homograph',
        lang: 'en',
        headword: 'etymology',
        candidates,
      },
    });

    await fireEvent.click(getByText('first sense'));

    expect(goto).toHaveBeenCalledWith('/tree/en/etymology?etym=a');
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
});
