import { test, expect } from '@playwright/test';

test('the landing card shows placeholder inputs over a blurred preview tree', async ({
  page,
}) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Etymyriad' })).toBeVisible();

  const headwordInput = page.getByLabel('Headword');
  await expect(headwordInput).toHaveValue('');
  await expect(headwordInput).toHaveAttribute('placeholder', 'etymology');

  const languageInput = page.getByLabel('Language code');
  await expect(languageInput).toHaveValue('');
  await expect(languageInput).toHaveAttribute('placeholder', 'en');

  await expect(
    page.getByRole('img', { name: 'Etymology tree', includeHidden: true }),
  ).toBeAttached();
});

test('hitting Explore with empty boxes animates into the default etymology (en) tree', async ({
  page,
}) => {
  await page.goto('/');
  const exploreButton = page.getByRole('button', { name: 'Explore' });

  // Same landing-page hydration race as theme-toggle.spec.ts: retry the
  // click until it actually reaches an attached listener.
  await expect(async () => {
    await exploreButton.click();
    await expect(page).toHaveURL(/\/tree\/en\/etymology$/, { timeout: 1000 });
  }).toPass();

  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'etymology',
  );
});
