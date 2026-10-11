import { test, expect } from '@playwright/test';

test('a blend shows each source word under a Blend label', async ({ page }) => {
  await page.goto('/tree/en/absquatulate');

  for (const source of ['abscond', 'squat', 'perambulate']) {
    await expect(
      page.getByRole('button', { name: `${source} (en)` }),
    ).toBeVisible();
  }
  await expect(page.locator('abbr[title="Blend"]').first()).toBeVisible();
  await expect(page.getByRole('alert')).not.toBeVisible();
});
