import { test, expect } from '@playwright/test';

test('ancestors walk past the old 5-hop depth cap', async ({ page }) => {
  // "king" -> ... -> Proto-Indo-European roots runs 8 hops deep in
  // the real dataset, well past the old shared DEFAULT_TREE_DEPTH=5.
  const lexemesRes = await page.request.get(
    '/api/lexemes?lang=en&headword=king',
  );
  const [{ id }] = await lexemesRes.json();

  const treeRes = await page.request.get(`/api/trees/${id}`);
  const slice = await treeRes.json();

  const minDepth = Math.min(
    ...slice.nodes.map((n: { depth: number }) => n.depth),
  );
  expect(minDepth).toBeLessThan(-5);
});
