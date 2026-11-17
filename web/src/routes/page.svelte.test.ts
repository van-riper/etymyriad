import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import Page from './+page.svelte';

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$app/state', () => ({ navigating: { to: null } }));

beforeEach(() => {
  goto.mockClear();
  vi.unstubAllGlobals();
});

describe('/ landing page', () => {
  it('renders the shared shell search form, not a standalone one', () => {
    const { getByLabelText, getByRole } = render(Page);

    expect(getByLabelText('Headword')).toBeInTheDocument();
    expect(getByRole('button', { name: 'Explore' })).toBeInTheDocument();
  });

  it('shows no node-count stat', () => {
    const { queryByText } = render(Page);

    expect(queryByText(/N\s*=/)).not.toBeInTheDocument();
  });

  it('navigates to the tree page on search', async () => {
    const { getByLabelText, getByRole } = render(Page);

    await fireEvent.input(getByLabelText('Headword'), {
      target: { value: 'father' },
    });
    await fireEvent.click(getByRole('button', { name: 'Explore' }));
    await vi.waitFor(() => expect(goto).toHaveBeenCalled());

    expect(goto).toHaveBeenCalledWith('/tree/en/father');
  });

  it('defaults to etymology/en when both boxes are left empty', async () => {
    const { getByRole } = render(Page);

    await fireEvent.click(getByRole('button', { name: 'Explore' }));
    await vi.waitFor(() => expect(goto).toHaveBeenCalled());

    expect(goto).toHaveBeenCalledWith('/tree/en/etymology');
  });

  it('fetches a random word and navigates to it', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ langCode: 'la', headword: 'pater' })),
      ),
    );

    const { getByRole } = render(Page);

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

    const { getByRole } = render(Page);

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
});
