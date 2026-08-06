import { test, expect } from '@playwright/test';

test('a leaf headword with no ancestors still renders', async ({ page }) => {
  await page.goto('/tree/en/abandoning');
  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'abandoning',
  );
  await expect(page.getByRole('alert')).not.toBeVisible();
});

test('multiple ancestor generations render and are clickable', async ({
  page,
}) => {
  await page.goto('/tree/en/etymology');
  await expect(
    page.getByRole('button', { name: 'ἐτυμολογία (grc)' }),
  ).toBeVisible();

  await page.getByRole('button', { name: 'etymologia (la)' }).click();

  await expect(page).toHaveURL(/\/tree\/la\/etymologia$/);
  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'etymologia',
  );
});
