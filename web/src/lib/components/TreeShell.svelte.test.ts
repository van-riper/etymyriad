import { describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import TreeShell from './TreeShell.svelte';
import type { Lexeme, LexemeSummary, TreeSlice } from '$lib/types';

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
  senses: [{ pos: 'noun', gloss: 'word origin study', sourceRef: 'ref' }],
};

const candidates: LexemeSummary[] = [
  { id: 'c1', etymKey: 'a', pos: 'noun', gloss: 'first sense' },
  { id: 'c2', etymKey: 'b', pos: 'verb', gloss: 'second sense' },
];

function baseProps() {
  return {
    lang: 'en',
    headword: 'etymology',
    loading: false,
    onsearch: vi.fn(),
    onrandom: vi.fn(),
  };
}

describe('TreeShell', () => {
  it('never renders a node-count stat', () => {
    const { queryByText } = render(TreeShell, {
      ...baseProps(),
      status: 'tree',
      slice,
      focusDetail,
    });

    expect(queryByText(/N\s*=/)).not.toBeInTheDocument();
  });

  it('calls onsearch when the search form is submitted with valid input', async () => {
    const onsearch = vi.fn();
    const { getByRole } = render(TreeShell, {
      ...baseProps(),
      onsearch,
      status: 'empty',
    });

    await fireEvent.click(getByRole('button', { name: 'Search' }));

    expect(onsearch).toHaveBeenCalled();
  });

  it('shows a validation error and skips onsearch for an empty headword', async () => {
    const onsearch = vi.fn();
    const { getByRole, getByLabelText, getByText } = render(TreeShell, {
      ...baseProps(),
      onsearch,
      headword: '',
      status: 'empty',
    });

    await fireEvent.input(getByLabelText('Headword'), {
      target: { value: '' },
    });
    await fireEvent.click(getByRole('button', { name: 'Search' }));

    expect(onsearch).not.toHaveBeenCalled();
    expect(getByText('Enter a word to look up.')).toBeInTheDocument();
  });

  it('calls onrandom with the current lang when "keep lang code" is checked', async () => {
    const onrandom = vi.fn();
    const { getByRole, getByLabelText } = render(TreeShell, {
      ...baseProps(),
      onrandom,
      status: 'empty',
    });

    await fireEvent.click(getByLabelText('Keep lang code'));
    await fireEvent.click(getByRole('button', { name: 'Random' }));

    expect(onrandom).toHaveBeenCalledWith('en');
  });

  it('calls onrandom with an empty lang when "keep lang code" is unchecked', async () => {
    const onrandom = vi.fn();
    const { getByRole } = render(TreeShell, {
      ...baseProps(),
      onrandom,
      status: 'empty',
    });

    await fireEvent.click(getByRole('button', { name: 'Random' }));

    expect(onrandom).toHaveBeenCalledWith('');
  });

  it('disables search and random while loading', () => {
    const { getByRole } = render(TreeShell, {
      ...baseProps(),
      loading: true,
      status: 'empty',
    });

    expect(getByRole('button', { name: 'Search' })).toBeDisabled();
    expect(getByRole('button', { name: 'Random' })).toBeDisabled();
  });

  it('renders a notfound message using the searched query, not the draft', () => {
    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'notfound',
      queryLang: 'en',
      queryHeadword: 'xyzzy',
    });

    expect(getByText(/No matches for "xyzzy" \(en\)/)).toBeInTheDocument();
  });

  it('renders homograph candidates and picks one', async () => {
    const onpickcandidate = vi.fn();
    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'homograph',
      queryLang: 'en',
      queryHeadword: 'etymology',
      candidates,
      onpickcandidate,
    });

    expect(getByText('first sense')).toBeInTheDocument();
    await fireEvent.click(getByText('first sense'));

    expect(onpickcandidate).toHaveBeenCalledWith('a');
  });

  it('renders the tree diagram and focus detail card', () => {
    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'tree',
      slice,
      focusDetail,
      onnodeclick: vi.fn(),
    });

    expect(getByText('etymologia (la)')).toBeInTheDocument();
    expect(getByText('English')).toBeInTheDocument();
    expect(getByText('word origin study')).toBeInTheDocument();
  });

  it('hides the legend by default', () => {
    const { queryByText } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    expect(queryByText(/cross-link/i)).not.toBeInTheDocument();
  });

  it('toggles the legend card open and closed', async () => {
    const { getByRole, getByText, queryByText } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    await fireEvent.click(getByRole('button', { name: 'Legend' }));
    expect(getByText(/cross-link/i)).toBeInTheDocument();

    await fireEvent.click(getByRole('button', { name: 'Legend' }));
    expect(queryByText(/cross-link/i)).not.toBeInTheDocument();
  });

  it('prefixes a reconstructed focus headword with an asterisk', () => {
    const reconstructedDetail: Lexeme = {
      ...focusDetail,
      headword: 'kreup-',
      isReconstructed: true,
    };

    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'tree',
      slice,
      focusDetail: reconstructedDetail,
    });

    expect(getByText('*kreup-')).toBeInTheDocument();
  });
});
