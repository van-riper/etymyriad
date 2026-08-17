import { test, expect } from '@playwright/test';

test('the legend card closes on Escape and returns focus to Legend', async ({
  page,
}) => {
  await page.goto('/tree/en/etymology');
  const legendButton = page.getByRole('button', { name: 'Legend' });
  const legendHeading = page.getByRole('heading', { name: 'Legend' });

  // Same hydration race as theme-toggle.spec.ts: retry the click until
  // it actually reaches an attached listener.
  await expect(async () => {
    await legendButton.click();
    await expect(legendHeading).toBeVisible({ timeout: 500 });
  }).toPass();

  await page.keyboard.press('Escape');
  await expect(legendHeading).not.toBeVisible();
  await expect(legendButton).toBeFocused();
});

test('the legend card closes on an outside click', async ({ page }) => {
  await page.goto('/tree/en/etymology');
  const legendButton = page.getByRole('button', { name: 'Legend' });
  const legendHeading = page.getByRole('heading', { name: 'Legend' });

  await expect(async () => {
    await legendButton.click();
    await expect(legendHeading).toBeVisible({ timeout: 500 });
  }).toPass();

  // Click a real element outside the popover, not a raw viewport
  // coordinate: the tree canvas is one big d3-zoom-bound SVG that
  // intercepts pointerdown for its own pan gesture, so a coordinate
  // click can land on the canvas and never reach bits-ui's
  // document-level outside-click listener.
  await page.getByText('English').click();
  await expect(legendHeading).not.toBeVisible();
});
