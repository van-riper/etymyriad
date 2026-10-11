import { test, expect } from '@playwright/test';

test('a contraction shows both source words under a Shortening label', async ({
  page,
}) => {
  // Section 2 of "its" is the obsolete contraction of "it is".
  await page.goto('/tree/en/its?etym=2');

  for (const source of ['it', 'is']) {
    await expect(
      page.getByRole('button', { name: `${source} (en)`, exact: true }),
    ).toBeVisible();
  }
  await expect(page.locator('abbr[title="Shortening"]').first()).toBeVisible();
});
