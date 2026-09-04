import { test, expect } from '@playwright/test';

// staniol (pl) has three direct lineage ancestors, including stannum
// (la) -- which is *also* a direct lineage ancestor of Stanniol (de),
// itself one of staniol's other direct ancestors. Wiktionary cites
// stannum at both distances. stannum should chain through
// Stanniol rather than render as a third tied sibling of it.
test('a lineage ancestor chains through a nearer ancestor instead of duplicating as a sibling', async ({
  page,
}) => {
  await page.goto('/tree/pl/staniol');
  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'staniol',
  );

  const stannum = page.getByText('stannum (la)', { exact: true });
  const stanniol = page.getByText('Stanniol (de)', { exact: true });
  await expect(stannum).toHaveCount(1);
  await expect(stanniol).toHaveCount(1);

  const stannumBox = await stannum.boundingBox();
  const stanniolBox = await stanniol.boundingBox();
  if (!stannumBox || !stanniolBox) throw new Error('node not rendered');
  // Ancestors render above the focus, so a deeper generation sits
  // higher up (smaller y) than a nearer one -- stannum chaining
  // through Stanniol means it is now one generation farther out.
  expect(stannumBox.y).toBeLessThan(stanniolBox.y);
});
