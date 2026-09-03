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
  // The server-rendered tree paints before hydration attaches any
  // handler, so a click landing in that window goes nowhere. The
  // client-computed fit transform replacing the identity one is the
  // signal that the diagram is live.
  await expect(page.locator('svg > g.zoom-layer')).not.toHaveAttribute(
    'transform',
    'translate(0,0) scale(1)',
  );

  await page.getByRole('button', { name: 'etymologia (la)' }).dblclick();

  await expect(page).toHaveURL(/\/tree\/la\/etymologia$/);
  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'etymologia',
  );
});

test('the diagram fills the canvas on first paint, not shrunken to a corner', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/tree/en/etymology');

  const canvasBox = await page.locator('.canvas').boundingBox();
  const svgBox = await page
    .getByRole('img', { name: 'Etymology tree' })
    .boundingBox();

  expect(canvasBox).not.toBeNull();
  expect(svgBox).not.toBeNull();
  expect(svgBox!.x).toBeLessThan(5);
  expect(svgBox!.width).toBeGreaterThan(canvasBox!.width * 0.95);
  expect(svgBox!.height).toBeGreaterThan(canvasBox!.height * 0.5);
});
