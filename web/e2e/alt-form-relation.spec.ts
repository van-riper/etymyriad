import { test, expect } from '@playwright/test';

test('a spelling variant shows its main form under an Alternative form label', async ({
  page,
}) => {
  await page.goto('/tree/en/hemo-');
  await expect(page.getByRole('button', { name: 'haemo- (en)' })).toBeVisible();
  await expect(
    page.locator('abbr[title="Alternative form"]').first(),
  ).toBeVisible();
  await expect(page.getByRole('alert')).not.toBeVisible();
});
