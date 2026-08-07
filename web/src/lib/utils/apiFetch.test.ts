import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const toastMock = {
  loading: vi.fn(() => 'toast-id'),
  dismiss: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
};

vi.mock('svelte-sonner', () => ({ toast: toastMock }));

async function loadApiFetch(browser: boolean) {
  vi.doMock('$app/environment', () => ({ browser }));
  vi.resetModules();
  return (await import('./apiFetch')).apiFetch;
}

describe('apiFetch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows no loading toast for a fast request', async () => {
    const apiFetch = await loadApiFetch(true);
    const fetchFn = vi.fn(async () => new Response('{}', { status: 200 }));

    await apiFetch('/api/x', fetchFn);

    expect(toastMock.loading).not.toHaveBeenCalled();
  });

  it('shows a loading toast for a slow request, dismissed on resolve', async () => {
    const apiFetch = await loadApiFetch(true);
    let resolveFetch!: (res: Response) => void;
    const fetchFn = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const pending = apiFetch('/api/x', fetchFn);
    await vi.advanceTimersByTimeAsync(1200);
    expect(toastMock.loading).toHaveBeenCalledWith(
      'The cluster is starting, please wait',
    );

    resolveFetch(new Response('{}', { status: 200 }));
    await pending;
    expect(toastMock.dismiss).toHaveBeenCalledWith('toast-id');
  });

  it('shows a warning toast on a 429 response', async () => {
    const apiFetch = await loadApiFetch(true);
    const fetchFn = vi.fn(
      async () =>
        new Response(JSON.stringify({ error: 'rate limited' }), {
          status: 429,
        }),
    );

    await apiFetch('/api/x', fetchFn);

    expect(toastMock.warning).toHaveBeenCalledWith(
      "You've sent too many requests",
    );
  });

  it('shows a generic error toast using the response body message', async () => {
    const apiFetch = await loadApiFetch(true);
    const fetchFn = vi.fn(
      async () =>
        new Response(JSON.stringify({ message: 'Enter a word to look up.' }), {
          status: 400,
        }),
    );

    await apiFetch('/api/x', fetchFn);

    expect(toastMock.error).toHaveBeenCalledWith('Enter a word to look up.');
  });

  it('falls back to a status-based message when the body has none', async () => {
    const apiFetch = await loadApiFetch(true);
    const fetchFn = vi.fn(async () => new Response('', { status: 500 }));

    await apiFetch('/api/x', fetchFn);

    expect(toastMock.error).toHaveBeenCalledWith('Request failed (500)');
  });

  it('never calls toast outside the browser', async () => {
    const apiFetch = await loadApiFetch(false);
    const fetchFn = vi.fn(async () => new Response('', { status: 500 }));

    const pending = apiFetch('/api/x', fetchFn);
    await vi.advanceTimersByTimeAsync(2000);
    await pending;

    expect(toastMock.loading).not.toHaveBeenCalled();
    expect(toastMock.error).not.toHaveBeenCalled();
  });
});
