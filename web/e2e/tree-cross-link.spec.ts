import { test, expect } from '@playwright/test';

// "meek" (en) has two ancestors that also cite each other directly
// (mjúkr <-> meukaz), a same-row cross-link.
test('a same-row cross-link renders as a routed path, not a straight line', async ({
  page,
}) => {
  await page.goto('/tree/en/meek');
  await expect(page.getByRole('heading', { level: 2 })).toContainText('meek');

  const crossLinks = page.locator('path.edge.cross-link');
  await expect(crossLinks.first()).toBeVisible();
  expect(await page.locator('line.edge.cross-link').count()).toBe(0);
});
