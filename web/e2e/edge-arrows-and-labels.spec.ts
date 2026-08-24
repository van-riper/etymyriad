import { test, expect } from '@playwright/test';

test('edges show a directional arrowhead and a relation-type label', async ({
  page,
}) => {
  await page.goto('/tree/en/etymology');

  const line = page.locator('path.edge.tree').first();
  await expect(line).toHaveAttribute('marker-end', 'url(#arrow-tree)');
  await expect(page.locator('marker#arrow-tree')).toHaveAttribute(
    'orient',
    'auto',
  );

  const abbr = page.locator('abbr').first();
  await expect(abbr).toBeVisible();
  await expect(abbr).toHaveAttribute('title', /.+/);
});
