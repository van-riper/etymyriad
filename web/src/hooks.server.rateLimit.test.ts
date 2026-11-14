import { beforeEach, describe, expect, it, vi } from 'vitest';

const limiters = vi.hoisted(() => ({ perClient: vi.fn(), global: vi.fn() }));

vi.mock('$app/env', () => ({ dev: false }));
vi.mock('cloudflare:workers', () => ({
  env: {
    RL_API: { limit: limiters.perClient },
    RL_GLOBAL: { limit: limiters.global },
  },
}));

import { handle } from './hooks.server';

type HandleArgs = Parameters<typeof handle>[0];

function makeArgs(pathname: string): HandleArgs {
  return {
    event: {
      url: new URL(`http://localhost${pathname}`),
      getClientAddress: () => '203.0.113.7',
    },
    resolve: vi.fn(async () => new Response('ok')),
  } as unknown as HandleArgs;
}

describe('handle rate limiting', () => {
  beforeEach(() => {
    limiters.perClient.mockResolvedValue({ success: true });
    limiters.global.mockResolvedValue({ success: true });
  });

  it('answers 429 when the per-client bucket is exhausted', async () => {
    limiters.perClient.mockResolvedValue({ success: false });
    const args = makeArgs('/api/terms');

    const response = await handle(args);

    expect(response.status).toBe(429);
    expect(args.resolve).not.toHaveBeenCalled();
  });

  it('answers 429 when the global bucket is exhausted', async () => {
    limiters.global.mockResolvedValue({ success: false });
    const args = makeArgs('/api/terms');

    const response = await handle(args);

    expect(response.status).toBe(429);
    expect(args.resolve).not.toHaveBeenCalled();
  });

  it('keys the per-client bucket on the client address', async () => {
    await handle(makeArgs('/api/terms'));

    expect(limiters.perClient).toHaveBeenCalledWith({ key: '203.0.113.7' });
    expect(limiters.global).toHaveBeenCalledWith({ key: 'global' });
  });

  it('lets a request through when both buckets allow it', async () => {
    const args = makeArgs('/api/terms');

    const response = await handle(args);

    expect(response.status).toBe(200);
    expect(args.resolve).toHaveBeenCalledOnce();
  });

  it('leaves non-API paths unlimited', async () => {
    const args = makeArgs('/tree/en/water');

    await handle(args);

    expect(limiters.perClient).not.toHaveBeenCalled();
    expect(args.resolve).toHaveBeenCalledOnce();
  });
});
