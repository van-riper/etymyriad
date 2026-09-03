import { test, expect } from '@playwright/test';

// The fitted transform can only be computed client-side (it needs the
// measured container size), so the server-rendered paint the browser
// shows before hydration has to be fitted some other way. Disabling JS
// pins the test to exactly that pre-hydration paint, rather than racing
// the hydration it would otherwise snap on.
test.use({ javaScriptEnabled: false });

test('the tree is fitted and centered before hydration, not clipped into the corner', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/tree/en/hydrophobia');

  const canvas = await page
    .locator('svg[aria-label="Etymology tree"]')
    .boundingBox();
  const tree = await page.locator('svg > g.zoom-layer').boundingBox();

  expect(canvas).not.toBeNull();
  expect(tree).not.toBeNull();

  // Centered: the browser's own viewBox fit (default
  // preserveAspectRatio) puts the tree's midpoint on the canvas's.
  const centerOffsetX =
    tree!.x + tree!.width / 2 - (canvas!.x + canvas!.width / 2);
  const centerOffsetY =
    tree!.y + tree!.height / 2 - (canvas!.y + canvas!.height / 2);
  expect(Math.abs(centerOffsetX)).toBeLessThan(20);
  expect(Math.abs(centerOffsetY)).toBeLessThan(20);

  // Fitted: none of it hangs off the canvas.
  expect(tree!.x).toBeGreaterThanOrEqual(canvas!.x - 2);
  expect(tree!.y).toBeGreaterThanOrEqual(canvas!.y - 2);
  expect(tree!.x + tree!.width).toBeLessThanOrEqual(
    canvas!.x + canvas!.width + 2,
  );
  expect(tree!.y + tree!.height).toBeLessThanOrEqual(
    canvas!.y + canvas!.height + 2,
  );
});
