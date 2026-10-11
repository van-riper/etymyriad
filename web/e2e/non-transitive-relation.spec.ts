import { test, expect } from '@playwright/test';

test('a calque shows its source but not the source ancestry', async ({
  page,
}) => {
  await page.goto('/tree/en/burgomaster');

  await expect(
    page.getByRole('button', { name: 'burgemeester (nl)' }),
  ).toBeVisible();
  await expect(page.locator('abbr[title="Calque"]').first()).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'borchmeester (dum)' }),
  ).toHaveCount(0);
});
