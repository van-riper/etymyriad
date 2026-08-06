import { test, expect } from '@playwright/test';

test('the random-word button navigates to a real word page', async ({
  page,
}) => {
  await page.goto('/');
  const randomButton = page.getByRole('button', { name: 'Random' });

  // Same landing-page hydration race as theme-toggle.spec.ts: retry
  // the click until navigation actually happens.
  await expect(async () => {
    await randomButton.click();
    await expect(page).toHaveURL(/\/tree\/[^/]+\/[^/]+$/, { timeout: 500 });
  }).toPass();

  const [, lang, headword] = new URL(page.url()).pathname
    .split('/')
    .slice(1);
  await expect(page.getByLabel('Language code')).toHaveValue(lang);
  await expect(page.getByLabel('Headword')).toHaveValue(
    decodeURIComponent(headword),
  );
});
