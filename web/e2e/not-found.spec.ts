import { test, expect } from '@playwright/test';

test('an unknown headword shows the not-found error, not a blank page', async ({
  page,
}) => {
  await page.goto('/tree/en/zzzznotarealword');
  await expect(page.getByRole('alert')).toContainText(
    'No matches for "zzzznotarealword" (en)',
  );
  await expect(page.getByRole('heading', { level: 2 })).not.toBeVisible();
});
