import { test, expect } from '@playwright/test';

// la:adamas is la:adamantem's real, direct ancestor, but grc:ἀδάμας
// (adamas's own ancestor) is also cited directly on en:adamant,
// landing grc:ἀδάμας at the same resolved depth as adamantem. An
// unguarded `direct` bucket would re-parent adamas onto grc:ἀδάμας
// instead, dropping adamantem's real parent edge entirely.
test('a real descendant renders under its ancestor despite a depth inversion', async ({
  page,
}) => {
  await page.goto('/tree/en/adamantium');
  await expect(page.getByRole('heading', { level: 2 })).toContainText(
    'adamantium',
  );

  const adamas = page.getByText('adamas (la)', { exact: true });
  const adamantem = page.getByText('adamantem (la)', { exact: true });
  await expect(adamas).toHaveCount(1);
  await expect(adamantem).toHaveCount(1);

  const adamasBox = await adamas.boundingBox();
  const adamantemBox = await adamantem.boundingBox();
  if (!adamasBox || !adamantemBox) throw new Error('node not rendered');
  // adamas is adamantem's ancestor, so it renders one generation
  // farther out (smaller x).
  expect(adamasBox.x).toBeLessThan(adamantemBox.x);
});
