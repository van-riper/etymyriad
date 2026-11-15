import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  match: vi.fn(),
  put: vi.fn(),
  waitUntil: vi.fn(),
  perClient: vi.fn(),
  global: vi.fn(),
}));

vi.mock('$app/env', () => ({ dev: false }));
vi.mock('cloudflare:workers', () => ({
  env: {
    RL_API: { limit: mocks.perClient },
    RL_GLOBAL: { limit: mocks.global },
  },
  waitUntil: mocks.waitUntil,
}));

import { handle } from './hooks.server';

type HandleArgs = Parameters<typeof handle>[0];

const PUBLIC = 'public, s-maxage=86400';

function makeArgs(
  pathname: string,
  respond: () => Response = () =>
    new Response('{"ok":true}', {
      headers: { 'cache-control': PUBLIC, 'content-type': 'application/json' },
    }),
  method = 'GET',
): HandleArgs {
  const url = new URL(`http://localhost${pathname}`);
  return {
    event: {
      url,
      request: new Request(url, { method }),
      getClientAddress: () => '203.0.113.7',
    },
    resolve: vi.fn(async () => respond()),
  } as unknown as HandleArgs;
}

describe('handle edge cache', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('caches', {
      default: { match: mocks.match, put: mocks.put },
    });
    mocks.match.mockResolvedValue(undefined);
    mocks.put.mockResolvedValue(undefined);
    mocks.perClient.mockResolvedValue({ success: true });
    mocks.global.mockResolvedValue({ success: true });
  });

  it('serves a cache hit without rate limiting or resolving', async () => {
    const cached = new Response('cached body');
    mocks.match.mockResolvedValue(cached);
    const args = makeArgs('/api/trees/1?section=0');

    const response = await handle(args);

    expect(response).toBe(cached);
    expect(mocks.match).toHaveBeenCalledWith(args.event.request);
    expect(args.resolve).not.toHaveBeenCalled();
    expect(mocks.perClient).not.toHaveBeenCalled();
    expect(mocks.global).not.toHaveBeenCalled();
  });

  it('stores a public 200 after the security headers are set', async () => {
    const args = makeArgs('/api/trees/1?section=0');

    const response = await handle(args);

    expect(mocks.put).toHaveBeenCalledOnce();
    const [request, stored] = mocks.put.mock.calls[0];
    expect(request).toBe(args.event.request);
    expect(stored).not.toBe(response);
    expect(stored.headers.get('x-content-type-options')).toBe('nosniff');
    expect(await stored.text()).toBe('{"ok":true}');
    expect(await response.text()).toBe('{"ok":true}');
  });

  it('keeps the store alive past the response with waitUntil', async () => {
    const stored = Promise.resolve();
    mocks.put.mockReturnValue(stored);

    await handle(makeArgs('/api/terms?lang=en&headword=water'));

    expect(mocks.waitUntil).toHaveBeenCalledWith(stored);
  });

  it.each([
    ['without a Cache-Control header', {}],
    ['marked private', { 'cache-control': 'private, max-age=60' }],
    ['marked no-store', { 'cache-control': 'public, no-store' }],
  ])('does not store a 200 %s', async (_label, headers) => {
    await handle(makeArgs('/api/terms', () => new Response('x', { headers })));

    expect(mocks.put).not.toHaveBeenCalled();
  });

  it('does not store an error response', async () => {
    await handle(
      makeArgs(
        '/api/terms',
        () =>
          new Response('{"message":"nope"}', {
            status: 404,
            headers: {
              'cache-control': PUBLIC,
              'content-type': 'application/json',
            },
          }),
      ),
    );

    expect(mocks.put).not.toHaveBeenCalled();
  });

  it('does not store a rate-limited response', async () => {
    mocks.perClient.mockResolvedValue({ success: false });

    const response = await handle(makeArgs('/api/terms'));

    expect(response.status).toBe(429);
    expect(mocks.put).not.toHaveBeenCalled();
  });

  it('leaves non-API paths out of the cache', async () => {
    await handle(makeArgs('/tree/en/water'));

    expect(mocks.match).not.toHaveBeenCalled();
    expect(mocks.put).not.toHaveBeenCalled();
  });

  it('leaves non-GET API requests out of the cache', async () => {
    await handle(makeArgs('/api/terms', undefined, 'POST'));

    expect(mocks.match).not.toHaveBeenCalled();
    expect(mocks.put).not.toHaveBeenCalled();
  });
});
