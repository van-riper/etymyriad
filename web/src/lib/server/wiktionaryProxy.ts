export interface WiktionaryPage {
  title: string;
  wikitext: string;
}

const API_BASE = 'https://en.wiktionary.org/w/api.php';
const USER_AGENT = 'etymyriad/0.1 (https://etymyriad.com)';
const CACHE_TTL_MS = 60 * 60 * 1000;

interface CacheEntry {
  page: WiktionaryPage | null;
  expiresAt: number;
}

// ponytail: in-memory, per-isolate cache -- fine for a single warm
// Cloudflare Worker instance under repeated lookups; move to the Cache
// API/KV if cross-request consistency across isolates starts to matter.
const cache = new Map<string, CacheEntry>();

// The one place that calls Wiktionary's live API (ETYM-138): every
// feature that needs a page's full wikitext (existence check, sense
// text) routes through here, so caching and the User-Agent Wikimedia's
// API etiquette asks for are enforced once instead of per caller.
export async function fetchWiktionaryPage(
  title: string,
): Promise<WiktionaryPage | null> {
  const cached = cache.get(title);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.page;
  }

  const params = new URLSearchParams({
    action: 'parse',
    page: title,
    prop: 'wikitext',
    format: 'json',
  });
  const response = await fetch(`${API_BASE}?${params}`, {
    headers: { 'User-Agent': USER_AGENT },
  });
  if (!response.ok) {
    throw new Error(`Wiktionary API error: ${response.status}`);
  }

  const body = (await response.json()) as {
    parse?: { title: string; wikitext: { '*': string } };
  };
  const page = body.parse
    ? { title: body.parse.title, wikitext: body.parse.wikitext['*'] }
    : null;

  cache.set(title, { page, expiresAt: Date.now() + CACHE_TTL_MS });
  return page;
}
