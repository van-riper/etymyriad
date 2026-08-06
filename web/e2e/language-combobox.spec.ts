import { test, expect } from '@playwright/test';

test('selecting a language from the combobox drives the search', async ({
  page,
}) => {
  await page.goto('/');
  const langInput = page.getByLabel('Language code');
  const spanishOption = page.getByRole('option', { name: /Spanish/i });

  // Same landing-page hydration race as theme-toggle.spec.ts: retry
  // filling the input until Svelte's oninput listener is attached and
  // actually opens the suggestion list.
  await expect(async () => {
    await langInput.fill('es');
    await expect(spanishOption).toBeVisible({ timeout: 500 });
  }).toPass();

  await spanishOption.click();
  await expect(langInput).toHaveValue('es');

  await page.getByLabel('Headword').fill('amor');
  await page.getByRole('button', { name: 'Search' }).click();

  await expect(page).toHaveURL(/\/tree\/es\/amor$/);
  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'amor',
  );
});
