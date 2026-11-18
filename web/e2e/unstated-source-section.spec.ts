import { test, expect } from '@playwright/test';

test('a descendant whose source etymology is not stated gets a dashed edge', async ({
  page,
}) => {
  await page.goto('/tree/en/or?etym=3');

  await expect(
    page.getByRole('button', { name: 'nor (en)', exact: true }),
  ).toBeVisible();
  await expect(page.locator('path.edge.unstated').first()).toBeVisible();
  await expect(
    page.getByTitle('Surface analysis; source etymology not stated'),
  ).not.toHaveCount(0);
});
