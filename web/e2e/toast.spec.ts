import { test, expect } from '@playwright/test';

test('a tree too large to fully fit shows a toast', async ({ page }) => {
  // "-ism" (en): a real, densely-connected word in the local dataset
  // whose slice is large enough to clamp at FLOOR_SCALE.
  await page.goto('/tree/en/-ism');

  await expect(
    page.getByText('This tree has too many nodes to fit on screen'),
  ).toBeVisible();
});
