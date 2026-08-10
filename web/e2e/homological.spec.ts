import { test, expect } from '@playwright/test';

test('homological renders all 3 direct ancestors, including the surf pieces', async ({
  page,
}) => {
  await page.goto('/tree/en/homological');
  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'homological',
  );

  await expect(
    page.getByRole('button', { name: 'ὁμός (grc)', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'homo- (en)', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'logical (en)', exact: true }),
  ).toBeVisible();
});
