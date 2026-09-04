import { describe, expect, it, vi } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import TreeShell from './TreeShell.svelte';
import type { Lexeme, LexemeSummary, TreeSlice } from '$lib/shared/types';

const slice: TreeSlice = {
  focusId: 'f',
  nodes: [
    {
      id: 'f',
      langCode: 'en',
      headword: 'etymology',
      isReconstructed: false,
      isRedlink: false,
      depth: 0,
    },
    {
      id: 'a1',
      langCode: 'la',
      headword: 'etymologia',
      isReconstructed: false,
      isRedlink: false,
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
  isRedlink: false,
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

  it('calls onsearch after the landing transition when the form is submitted with valid input', async () => {
    vi.useFakeTimers();
    const onsearch = vi.fn();
    const { getByRole } = render(TreeShell, {
      ...baseProps(),
      onsearch,
      status: 'empty',
    });

    await fireEvent.click(getByRole('button', { name: 'Explore' }));
    expect(onsearch).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(350);
    expect(onsearch).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('defaults to the default lang/headword and still calls onsearch when both boxes are empty', async () => {
    vi.useFakeTimers();
    const onsearch = vi.fn();
    const { getByRole } = render(TreeShell, {
      ...baseProps(),
      onsearch,
      lang: '',
      headword: '',
      status: 'empty',
    });

    await fireEvent.click(getByRole('button', { name: 'Explore' }));
    await vi.advanceTimersByTimeAsync(350);

    expect(onsearch).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('shows placeholder text rather than a bound value for empty lang/headword', () => {
    const { getByLabelText } = render(TreeShell, {
      ...baseProps(),
      lang: '',
      headword: '',
      status: 'empty',
    });

    const headwordInput = getByLabelText('Headword') as HTMLInputElement;
    expect(headwordInput.value).toBe('');
    expect(headwordInput.placeholder).toBe('etymology');
  });

  it('has a visible label associated with the headword input', () => {
    const { getByText, getByLabelText } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    const label = getByText('Headword', { selector: 'label' });
    expect(label).toBeVisible();
    const input = getByLabelText('Headword') as HTMLInputElement;
    expect(label.getAttribute('for')).toBe(input.id);
  });

  it('renders a blurred, non-interactive preview tree behind the landing card', () => {
    const { getByRole } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    const preview = getByRole('img', {
      name: 'Etymology tree',
      hidden: true,
    });
    expect(preview.closest('.preview-tree')).not.toBeNull();
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

  it('calls onrandom with "en" when "keep lang code" is checked but the lang box is empty', async () => {
    const onrandom = vi.fn();
    const { getByRole, getByLabelText } = render(TreeShell, {
      ...baseProps(),
      lang: '',
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

    expect(getByRole('button', { name: 'Explore' })).toBeDisabled();
    expect(getByRole('button', { name: 'Random' })).toBeDisabled();
  });

  it('does not show a spinner right when loading starts', async () => {
    vi.useFakeTimers();
    const { getByRole, rerender } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    await rerender({ ...baseProps(), loading: true, status: 'empty' });

    expect(() => getByRole('status', { name: 'Loading' })).toThrow();
    vi.useRealTimers();
  });

  it('shows a spinner once loading has run past 300ms', async () => {
    vi.useFakeTimers();
    const { getByRole, rerender } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    await rerender({ ...baseProps(), loading: true, status: 'empty' });
    await vi.advanceTimersByTimeAsync(300);

    expect(getByRole('status', { name: 'Loading' })).toBeInTheDocument();
    vi.useRealTimers();
  });

  it('hides the spinner immediately once loading ends, even mid-delay', async () => {
    vi.useFakeTimers();
    const { getByRole, rerender } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    await rerender({ ...baseProps(), loading: true, status: 'empty' });
    await vi.advanceTimersByTimeAsync(200);
    await rerender({ ...baseProps(), loading: false, status: 'empty' });
    await vi.advanceTimersByTimeAsync(300);

    expect(() => getByRole('status', { name: 'Loading' })).toThrow();
    vi.useRealTimers();
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

  it('calls onhomographescape on Escape within the homograph-picker', async () => {
    const onhomographescape = vi.fn();
    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'homograph',
      queryLang: 'en',
      queryHeadword: 'etymology',
      candidates,
      onhomographescape,
    });

    await fireEvent.keyDown(getByText('first sense'), { key: 'Escape' });

    expect(onhomographescape).toHaveBeenCalled();
  });

  it('calls ondetailescape on Escape while the detail card is shown', async () => {
    const ondetailescape = vi.fn();
    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'tree',
      slice,
      focusDetail,
      ondetailescape,
    });

    await fireEvent.keyDown(getByText('English'), { key: 'Escape' });

    expect(ondetailescape).toHaveBeenCalled();
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

    expect(queryByText(/Collapsed siblings/i)).not.toBeInTheDocument();
  });

  it('toggles the legend card open and closed', async () => {
    const { getByRole, getByText, queryByText } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    await fireEvent.click(getByRole('button', { name: 'Legend' }));
    expect(getByText(/Collapsed siblings/i)).toBeInTheDocument();

    await fireEvent.click(getByRole('button', { name: 'Legend' }));
    expect(queryByText(/Collapsed siblings/i)).not.toBeInTheDocument();
  });

  it('closes the legend card on Escape', async () => {
    const { getByRole, getByText, queryByText } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    await fireEvent.click(getByRole('button', { name: 'Legend' }));
    expect(getByText(/Collapsed siblings/i)).toBeInTheDocument();

    await fireEvent.keyDown(getByText(/Collapsed siblings/i), {
      key: 'Escape',
    });
    await waitFor(() =>
      expect(queryByText(/Collapsed siblings/i)).not.toBeInTheDocument(),
    );
  });

  // Outside-click dismissal is covered by e2e/legend-popover.spec.ts
  // instead: bits-ui's dismissable layer relies on real pointer/focus
  // semantics jsdom's fireEvent doesn't faithfully reproduce.

  it('returns focus to the Legend button after closing the legend card', async () => {
    const { getByRole } = render(TreeShell, {
      ...baseProps(),
      status: 'empty',
    });

    const legendButton = getByRole('button', { name: 'Legend' });
    // jsdom's fireEvent.click, unlike a real click, does not itself
    // move focus, so focus explicitly first to give the focus scope a
    // real "previously focused element" to restore on close.
    legendButton.focus();
    await fireEvent.click(legendButton);
    await fireEvent.click(legendButton);

    await waitFor(() => expect(legendButton).toHaveFocus());
  });

  it('prefixes a reconstructed focus headword with an asterisk', () => {
    const reconstructedDetail: Lexeme = {
      ...focusDetail,
      headword: 'kreup-',
      isReconstructed: true,
      isRedlink: false,
    };

    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'tree',
      slice,
      focusDetail: reconstructedDetail,
    });

    expect(getByText('*kreup-')).toBeInTheDocument();
  });

  it('shows a redlink tag for a redlink focus word', () => {
    const redlinkDetail: Lexeme = {
      ...focusDetail,
      isRedlink: true,
    };

    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'tree',
      slice,
      focusDetail: redlinkDetail,
    });

    expect(getByText('redlink')).toBeInTheDocument();
  });

  it('shows both tags for a reconstructed redlink focus word', () => {
    const bothDetail: Lexeme = {
      ...focusDetail,
      headword: 'kreup-',
      isReconstructed: true,
      isRedlink: true,
    };

    const { getByText } = render(TreeShell, {
      ...baseProps(),
      status: 'tree',
      slice,
      focusDetail: bothDetail,
    });

    expect(getByText('*kreup-')).toBeInTheDocument();
    expect(getByText('reconstructed')).toBeInTheDocument();
    expect(getByText('redlink')).toBeInTheDocument();
  });

  it('shows no redlink tag for a non-redlink focus word', () => {
    const { queryByText } = render(TreeShell, {
      ...baseProps(),
      status: 'tree',
      slice,
      focusDetail,
    });

    expect(queryByText('redlink')).not.toBeInTheDocument();
  });
});
