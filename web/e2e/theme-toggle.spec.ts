import { test, expect } from '@playwright/test';

test('theme toggle cycles mode and persists across a reload', async ({
  page,
}) => {
  await page.goto('/');
  const toggle = page.getByRole('button', { name: /^Theme: Auto/ });
  await expect(toggle).toBeVisible();

  // The landing page has no async load fn, so it can render before
  // Svelte finishes hydrating -- retry the click until it actually
  // reaches an attached listener, instead of a fixed sleep.
  await expect(async () => {
    await toggle.click();
    await expect(
      page.getByRole('button', { name: /^Theme: Light/ }),
    ).toBeVisible({ timeout: 500 });
  }).toPass();

  await page.reload();
  await expect(
    page.getByRole('button', { name: /^Theme: Light/ }),
  ).toBeVisible();
});
