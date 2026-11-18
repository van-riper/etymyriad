import { test, expect } from '@playwright/test';

test('an ancestor with several etymologies is not climbed', async ({
  page,
}) => {
  await page.goto('/tree/en/nor?etym=1');

  await expect(
    page.getByRole('button', { name: 'or (en)', exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'aurum (la)' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'oþþe (ang)' })).toHaveCount(0);
});
