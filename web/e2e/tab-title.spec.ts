import { test, expect } from '@playwright/test';

test('tab title reflects the selected lexeme', async ({ page }) => {
  await page.goto('/tree/en/etymology');
  await expect(page).toHaveTitle('etymology (English) · Etymyriad');

  await page.getByRole('button', { name: 'etymologia (la)' }).dblclick();
  await expect(page).toHaveTitle('etymologia (Latin) · Etymyriad');
});

test('single-clicking a node does not change the tab title', async ({
  page,
}) => {
  await page.goto('/tree/en/etymology');
  await expect(page).toHaveTitle('etymology (English) · Etymyriad');

  await page.getByRole('button', { name: 'etymologia (la)' }).click();
  // The click's detail-panel update is debounced and async; wait for
  // it to land before asserting the title held steady, or the
  // assertion below could pass trivially by checking too early.
  await expect(page.locator('.detail-headword')).toContainText('etymologia');
  await expect(page).toHaveTitle('etymology (English) · Etymyriad');
});
