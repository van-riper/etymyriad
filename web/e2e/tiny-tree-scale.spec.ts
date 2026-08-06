import { test, expect } from '@playwright/test';
import { NODE_WIDTH, NODE_HEIGHT } from '../src/lib/utils/treeLayout';

test('a genuinely tiny tree stays near native node size, not blown up to fill the viewport', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto('/tree/en/shocks');

  const node = page.getByRole('button', {
    name: 'shocks (en)',
    exact: true,
  });
  await expect(node).toBeVisible();
  const zoomLayer = page.locator('svg > g').first();
  await expect(zoomLayer).not.toHaveAttribute(
    'transform',
    'translate(0,0) scale(1)',
  );
  const box = await node.boundingBox();

  expect(box).not.toBeNull();
  expect(box!.width).toBeLessThanOrEqual(2 * NODE_WIDTH);
  expect(box!.height).toBeLessThanOrEqual(2 * NODE_HEIGHT);
});
