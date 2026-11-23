import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import type { TreeSlice } from '../src/lib/shared/types.ts';
import { DEFAULT_HEADWORD, DEFAULT_LANG } from '../src/lib/tree/defaultTree.ts';

type Fetch = (url: string) => Promise<Response>;

async function getJson<T>(fetchJson: Fetch, url: string): Promise<T> {
  const response = await fetchJson(url);
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

export async function fetchDefaultTreeSlice(
  baseUrl: string,
  lang: string,
  headword: string,
  fetchJson: Fetch = fetch,
): Promise<TreeSlice> {
  const query = new URLSearchParams({ lang, headword, section: '0' });
  const matches = await getJson<{ id: number }[]>(
    fetchJson,
    `${baseUrl}/api/terms?${query}`,
  );
  if (matches.length === 0)
    throw new Error(`No term found for ${lang}:${headword}`);
  return getJson<TreeSlice>(
    fetchJson,
    `${baseUrl}/api/trees/${matches[0].id}?section=0`,
  );
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const baseUrl = process.argv[2] ?? 'http://localhost:5173';
  const slice = await fetchDefaultTreeSlice(
    baseUrl,
    DEFAULT_LANG,
    DEFAULT_HEADWORD,
  );
  const outputPath = new URL(
    '../src/lib/tree/defaultTree.json',
    import.meta.url,
  );
  writeFileSync(outputPath, JSON.stringify(slice));
}
