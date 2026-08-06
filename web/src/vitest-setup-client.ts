import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Every page renders LanguageCombobox, which fetches '/api/languages' on
// mount. jsdom has no origin to resolve a relative URL against, so an
// unmocked fetch here throws ERR_INVALID_URL as an unhandled rejection.
// A plain assignment (not vi.stubGlobal) so a test file's own
// vi.unstubAllGlobals() reverts *to* this default instead of past it; a
// test asserting on fetch behavior overrides it with its own
// vi.stubGlobal('fetch', ...).
globalThis.fetch = vi.fn(() =>
  Promise.resolve({ ok: true, json: async () => [] }),
) as unknown as typeof fetch;
