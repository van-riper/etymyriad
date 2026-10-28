import { test, expect } from '@playwright/test';

test('the CSP restricts base-uri and form-action to self', async ({
  request,
}) => {
  const response = await request.get('/');
  const csp = response.headers()['content-security-policy'];
  expect(csp).toContain("base-uri 'self'");
  expect(csp).toContain("form-action 'self'");
});

for (const path of ['/', '/api/languages']) {
  test(`${path} sets X-Content-Type-Options: nosniff`, async ({ request }) => {
    const response = await request.get(path);
    expect(response.headers()['x-content-type-options']).toBe('nosniff');
  });
}
