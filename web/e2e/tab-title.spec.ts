import { test, expect } from '@playwright/test';

test('tab title reflects the selected lexeme', async ({ page }) => {
  await page.goto('/tree/en/etymology');
  await expect(page).toHaveTitle('etymology (English) · Etymyriad');

  await page.getByRole('button', { name: 'etymologia (la)' }).dblclick();
  await expect(page).toHaveTitle('etymologia (Latin) · Etymyriad');
});
