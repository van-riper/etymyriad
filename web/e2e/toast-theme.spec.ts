import { test, expect } from '@playwright/test';

test.describe('toast notifications follow the flexoki theme', () => {
  for (const theme of ['light', 'dark'] as const) {
    test(`in ${theme} mode`, async ({ page }) => {
      // A tiny viewport forces zoomFit's naturalScale below FLOOR_SCALE,
      // which reliably fires the real "too many nodes" info toast
      // (TreeDiagram.svelte) regardless of which word is loaded.
      await page.setViewportSize({ width: 300, height: 300 });
      await page.goto('/tree/en/etymology');
      await page.evaluate((t) => {
        localStorage.setItem('etymyriad-theme', t);
      }, theme);
      await page.reload();

      await page.locator('[data-sonner-toast]').waitFor();

      const vars = await page.evaluate(() => {
        const root = getComputedStyle(document.documentElement);
        const toaster = getComputedStyle(
          document.querySelector('[data-sonner-toaster]')!,
        );
        return {
          bg2: root.getPropertyValue('--bg-2').trim(),
          border: root.getPropertyValue('--ui-border').trim(),
          accent: root.getPropertyValue('--accent').trim(),
          normalBg: toaster.getPropertyValue('--normal-bg').trim(),
          normalBorder: toaster.getPropertyValue('--normal-border').trim(),
          infoBorder: toaster.getPropertyValue('--info-border').trim(),
        };
      });

      expect(vars.normalBg).toBe(vars.bg2);
      expect(vars.normalBorder).toBe(vars.border);
      expect(vars.infoBorder).toBe(vars.accent);
    });
  }
});
