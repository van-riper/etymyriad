import { test, expect } from '@playwright/test';

test('an unmatched route shows the themed error page, not the bare SvelteKit default', async ({
  page,
}) => {
  // A plain 404 network log is expected for this navigation itself;
  // only flag CSP violations (a broken CSP directive would silently
  // break the theme script, fonts, or toast styling).
  const cspErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && /content security policy/i.test(msg.text())) {
      cspErrors.push(msg.text());
    }
  });

  const response = await page.goto('/nonexistent');
  expect(response?.status()).toBe(404);

  await expect(page.getByRole('heading', { name: '404' })).toBeVisible();
  await expect(page.getByText('Not Found')).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'View source on GitHub' }),
  ).toBeVisible();

  expect(cspErrors, cspErrors.join('\n')).toEqual([]);
});

test('an unmatched /api/* route returns a JSON error, not HTML', async ({
  request,
}) => {
  const response = await request.get('/api/nonexistent');
  expect(response.status()).toBe(404);
  expect(response.headers()['content-type']).toContain('application/json');
  expect(await response.json()).toEqual({ message: 'Not Found' });
});

test('an unsupported method on a real /api/* route returns a JSON error', async ({
  request,
}) => {
  const response = await request.post('/api/languages');
  expect(response.status()).toBe(405);
  expect(response.headers()['content-type']).toContain('application/json');
  expect(await response.json()).toEqual({
    message: 'POST method not allowed',
  });
});
