import { describe, expect, it, vi } from 'vitest';
import { handle } from './hooks.server';

type HandleArgs = Parameters<typeof handle>[0];

function makeEvent(pathname: string): HandleArgs['event'] {
  return {
    url: new URL(`http://localhost${pathname}`),
    platform: undefined,
    getClientAddress: () => '127.0.0.1',
  } as HandleArgs['event'];
}

describe('handle', () => {
  it('converts a non-JSON 404 under /api/* into {message} JSON', async () => {
    const resolve = vi.fn(
      async () =>
        new Response('Not Found', {
          status: 404,
          statusText: 'Not Found',
          headers: { 'content-type': 'text/html' },
        }),
    );

    const response = await handle({
      event: makeEvent('/api/nonexistent'),
      resolve,
    } as HandleArgs);

    expect(response.status).toBe(404);
    expect(response.headers.get('content-type')).toContain('application/json');
    expect(await response.json()).toEqual({ message: 'Not Found' });
  });

  it('converts a non-JSON 405 under /api/* into {message} JSON, keeping Allow', async () => {
    const resolve = vi.fn(
      async () =>
        new Response('POST method not allowed', {
          status: 405,
          headers: { 'content-type': 'text/plain', allow: 'GET, HEAD' },
        }),
    );

    const response = await handle({
      event: makeEvent('/api/languages'),
      resolve,
    } as HandleArgs);

    expect(response.status).toBe(405);
    expect(await response.json()).toEqual({
      message: 'POST method not allowed',
    });
    expect(response.headers.get('allow')).toBe('GET, HEAD');
  });

  it('leaves an already-JSON /api/* error response untouched', async () => {
    const resolve = vi.fn(
      async () =>
        new Response(JSON.stringify({ message: 'bad input' }), {
          status: 400,
          headers: { 'content-type': 'application/json' },
        }),
    );

    const response = await handle({
      event: makeEvent('/api/lexemes'),
      resolve,
    } as HandleArgs);

    expect(await response.json()).toEqual({ message: 'bad input' });
  });

  it('does not touch a successful /api/* response', async () => {
    const resolve = vi.fn(
      async () =>
        new Response(JSON.stringify([1, 2]), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
    );

    const response = await handle({
      event: makeEvent('/api/languages'),
      resolve,
    } as HandleArgs);

    expect(await response.json()).toEqual([1, 2]);
  });

  it('does not normalize a non-api 404 (pages get their own +error.svelte)', async () => {
    const resolve = vi.fn(
      async () =>
        new Response('<html>404</html>', {
          status: 404,
          headers: { 'content-type': 'text/html' },
        }),
    );

    const response = await handle({
      event: makeEvent('/nonexistent'),
      resolve,
    } as HandleArgs);

    expect(response.headers.get('content-type')).toContain('text/html');
  });

  it('sets Referrer-Policy and X-Frame-Options on every response', async () => {
    const resolve = vi.fn(async () => new Response('ok', { status: 200 }));

    const response = await handle({
      event: makeEvent('/'),
      resolve,
    } as HandleArgs);

    expect(response.headers.get('referrer-policy')).toBe(
      'strict-origin-when-cross-origin',
    );
    expect(response.headers.get('x-frame-options')).toBe('DENY');
  });
});
