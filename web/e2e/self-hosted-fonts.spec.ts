import { test, expect } from '@playwright/test';

const GOOGLE_FONT_HOSTS = /fonts\.(googleapis|gstatic)\.com/;

for (const path of ['/', '/tree/en/king']) {
  test(`${path} makes no request to a Google font host`, async ({ page }) => {
    const googleRequests: string[] = [];
    page.on('request', (request) => {
      if (GOOGLE_FONT_HOSTS.test(request.url())) {
        googleRequests.push(request.url());
      }
    });

    await page.goto(path);
    await page.waitForLoadState('networkidle');

    expect(googleRequests).toEqual([]);
  });
}

test('the CSP no longer lists Google font origins', async ({ request }) => {
  const response = await request.get('/');
  const csp = response.headers()['content-security-policy'];
  expect(csp).not.toMatch(GOOGLE_FONT_HOSTS);
});

const SCRIPT_FONT_SAMPLES: Record<string, string> = {
  'Noto Sans Avestan': '\u{10B00}',
  'Noto Sans Brahmi': '\u{11005}',
  'Noto Sans Cuneiform': '\u{12000}',
  'Noto Sans Egyptian Hieroglyphs': '\u{13000}',
  'Noto Sans Gothic': '\u{10330}',
  'Noto Sans Imperial Aramaic': '\u{10840}',
  'Noto Sans Kharoshthi': '\u{10A00}',
  'Noto Sans Old Italic': '\u{10300}',
  'Noto Sans Old Persian': '\u{103A0}',
  'Noto Sans Phoenician': '\u{10900}',
  'Noto Sans Sharada': '\u{11180}',
};

for (const [family, glyph] of Object.entries(SCRIPT_FONT_SAMPLES)) {
  test(`${family} loads from this origin for its own script`, async ({
    page,
  }) => {
    const fontUrls: string[] = [];
    page.on('request', (request) => {
      if (request.resourceType() === 'font') {
        fontUrls.push(request.url());
      }
    });

    await page.goto('/');
    const loadedFaces = await page.evaluate(
      async ([name, sample]) => {
        const faces = await document.fonts.load(`16px "${name}"`, sample);
        return faces.map((face) => face.status);
      },
      [family, glyph],
    );

    expect(loadedFaces).toEqual(['loaded']);
    const origin = new URL(page.url()).origin;
    for (const url of fontUrls) {
      expect(url.startsWith(origin)).toBe(true);
    }
  });
}

test('Inter loads from this origin', async ({ page }) => {
  await page.goto('/');
  const loadedFamilies = await page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts]
      .filter((font) => font.status === 'loaded')
      .map((font) => font.family);
  });
  expect(loadedFamilies).toContain('Inter');
});
