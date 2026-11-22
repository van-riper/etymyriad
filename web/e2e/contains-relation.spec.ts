import { test, expect } from '@playwright/test';

test('a zh word shows the character listing it under a Contains label', async ({
  page,
}) => {
  await page.goto('/tree/zh/一團火');
  await expect(
    page.getByRole('button', { name: '火 (zh)', exact: true }),
  ).toBeVisible();
  await expect(page.locator('abbr[title="Contains"]').first()).toBeVisible();
  await expect(page.getByRole('alert')).not.toBeVisible();
});

test('a zh character caps its many listed compounds behind an overflow', async ({
  page,
}) => {
  await page.goto('/tree/zh/火');
  await expect(page.locator('abbr[title="Contains"]').first()).toBeVisible();
  await expect(
    page.getByRole('button', { name: /^\+\d+ more$/ }),
  ).toBeVisible();
  await expect(page.getByRole('alert')).not.toBeVisible();
});
