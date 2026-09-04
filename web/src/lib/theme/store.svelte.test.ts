import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

class FakeStorage {
  private store = new Map<string, string>();
  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }
  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
  clear(): void {
    this.store.clear();
  }
}

class FakeMediaQueryList {
  matches: boolean;
  private listeners: Array<(event: { matches: boolean }) => void> = [];
  constructor(matches: boolean) {
    this.matches = matches;
  }
  addEventListener(
    _type: string,
    listener: (event: { matches: boolean }) => void,
  ): void {
    this.listeners.push(listener);
  }
  removeEventListener(): void {}
  emit(matches: boolean): void {
    this.matches = matches;
    for (const listener of this.listeners) listener({ matches });
  }
}

let storage: FakeStorage;
let mediaQuery: FakeMediaQueryList;

// theme.svelte.ts reads localStorage/matchMedia at module-eval time (for
// the initial mode/system-preference snapshot), so each test needs a
// fresh module instance: vi.resetModules + a dynamic import per test,
// rather than one top-level import shared across the file.
async function freshTheme() {
  vi.resetModules();
  return await import('./store.svelte');
}

beforeEach(() => {
  storage = new FakeStorage();
  mediaQuery = new FakeMediaQueryList(false);
  vi.stubGlobal('localStorage', storage);
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => mediaQuery),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('theme', () => {
  it('defaults to system mode with no stored preference', async () => {
    const { theme } = await freshTheme();
    expect(theme.mode).toBe('system');
  });

  it('resolves system mode from matchMedia', async () => {
    mediaQuery = new FakeMediaQueryList(true);
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => mediaQuery),
    );
    const { theme } = await freshTheme();
    expect(theme.resolved).toBe('dark');
  });

  it('reads a stored mode over the system default', async () => {
    storage.setItem('etymyriad-theme', 'dark');
    const { theme } = await freshTheme();
    expect(theme.mode).toBe('dark');
    expect(theme.resolved).toBe('dark');
  });

  it('ignores a corrupt stored value and falls back to system', async () => {
    storage.setItem('etymyriad-theme', 'purple');
    const { theme } = await freshTheme();
    expect(theme.mode).toBe('system');
  });

  it('cycles light -> dark -> system -> light', async () => {
    storage.setItem('etymyriad-theme', 'light');
    const { theme } = await freshTheme();
    expect(theme.mode).toBe('light');
    theme.cycle();
    expect(theme.mode).toBe('dark');
    theme.cycle();
    expect(theme.mode).toBe('system');
    theme.cycle();
    expect(theme.mode).toBe('light');
  });

  it('persists the mode across a simulated reload', async () => {
    storage.setItem('etymyriad-theme', 'light');
    const first = await freshTheme();
    first.theme.cycle();
    expect(storage.getItem('etymyriad-theme')).toBe('dark');

    const second = await freshTheme();
    expect(second.theme.mode).toBe('dark');
  });

  it('updates resolved live when the system preference changes', async () => {
    const { theme } = await freshTheme();
    expect(theme.resolved).toBe('light');
    mediaQuery.emit(true);
    expect(theme.resolved).toBe('dark');
  });
});
