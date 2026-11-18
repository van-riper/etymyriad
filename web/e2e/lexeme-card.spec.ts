import { test, expect } from '@playwright/test';

const headwords = [
  { lang: 'grc', headword: 'ἐτυμολογία', label: 'ἐτυμολογία (grc)' },
  { lang: 'ine-pro', headword: 'h₂ékʷeh₂', label: '*h₂ékʷeh₂ (ine-pro)' },
  { lang: 'en', headword: 'unetymologically', label: 'unetymologically (en)' },
  {
    lang: 'ru',
    headword: 'превысокомногорассмотрительствующий',
    label: 'превысокомногорассмотрительствующий (ru)',
  },
];

for (const { lang, headword, label } of headwords) {
  test(`the ${label} card wraps its headword inside the card`, async ({
    page,
  }) => {
    await page.goto(`/tree/${lang}/${encodeURIComponent(headword)}`);

    const card = page.getByRole('button', { name: label, exact: true });
    await expect(card).toBeVisible();

    const rectBox = (await card.locator('rect').boundingBox())!;
    const headwordBox = (await card.locator('.headword').boundingBox())!;
    const headwordEl = card.locator('.headword');
    const scrollWidth = await headwordEl.evaluate((el) => el.scrollWidth);
    const clientWidth = await headwordEl.evaluate((el) => el.clientWidth);

    const cardEl = card.locator('.card');
    const cardFits = await cardEl.evaluate(
      (el) => el.scrollHeight <= el.clientHeight + 1,
    );

    expect(cardFits).toBe(true);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
    expect(headwordBox.x).toBeGreaterThanOrEqual(rectBox.x);
    expect(headwordBox.y).toBeGreaterThanOrEqual(rectBox.y);
    expect(headwordBox.x + headwordBox.width).toBeLessThanOrEqual(
      rectBox.x + rectBox.width,
    );
    expect(headwordBox.y + headwordBox.height).toBeLessThanOrEqual(
      rectBox.y + rectBox.height,
    );
  });
}

test('every card in a tree renders at the same width', async ({ page }) => {
  await page.goto('/tree/en/etymology');
  const cards = page.locator('.node:not(.overflow) rect');
  await expect(cards.first()).toBeVisible();

  const widths = await cards.evaluateAll((rects) =>
    rects.map((rect) => rect.getAttribute('width')),
  );

  expect(widths.length).toBeGreaterThan(1);
  expect(new Set(widths).size).toBe(1);
});

test('every card fits its rows inside its box', async ({ page }) => {
  await page.goto('/tree/en/etymology');
  const cards = page.locator('.node:not(.overflow) .card');
  await expect(cards.first()).toBeVisible();

  const overflowing = await cards.evaluateAll((elements) =>
    elements
      .filter((el) => el.scrollHeight > el.clientHeight + 1)
      .map((el) => el.textContent),
  );

  expect(overflowing).toEqual([]);
});
