import { test, expect } from '@playwright/test';

test('a node with a long headword sizes its box to fit the label', async ({
  page,
}) => {
  const headword = 'превысокомногорассмотрительствующий';
  await page.goto(`/tree/ru/${encodeURIComponent(headword)}`);

  const node = page.getByRole('button', {
    name: `${headword} (ru)`,
    exact: true,
  });
  await expect(node).toBeVisible();

  const rectBox = await node.locator('rect').boundingBox();
  const textBox = await node.locator('text').boundingBox();

  expect(rectBox).not.toBeNull();
  expect(textBox).not.toBeNull();
  // The whole point of ETYM-153: the box grows to fit the label
  // instead of the label spilling past a fixed floor width.
  expect(rectBox!.width).toBeGreaterThan(120);
  expect(rectBox!.width).toBeGreaterThanOrEqual(textBox!.width);
});
