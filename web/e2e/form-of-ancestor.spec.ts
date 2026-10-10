import { test, expect } from '@playwright/test';

test('a participle shows its lemma as an ancestor', async ({ page }) => {
  await page.goto('/tree/it/avvertito');
  await expect(
    page.getByRole('button', { name: 'avvertire (it)' }),
  ).toBeVisible();
  await expect(page.getByRole('alert')).not.toBeVisible();
});
