import { test, expect } from '@playwright/test';

test('home page loads and shows the landing copy', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Etymyriad' })).toBeVisible();
  await expect(page.getByLabel('Headword')).toBeVisible();
});

test('a word page renders its tree', async ({ page }) => {
  await page.goto('/tree/en/etymology');
  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'etymology',
  );
});
