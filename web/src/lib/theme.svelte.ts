export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'etymyriad-theme';
const MODE_ORDER: ThemeMode[] = ['light', 'dark', 'system'];

// Bare global identifiers (not window.localStorage/window.matchMedia) so
// tests can stub them with vi.stubGlobal without needing a real `window`
// -- this repo's vitest config runs in plain Node (environment: 'node'),
// not jsdom.
function hasStorage(): boolean {
  return typeof localStorage !== 'undefined';
}

function hasMatchMedia(): boolean {
  return typeof matchMedia !== 'undefined';
}

function isThemeMode(value: string | null): value is ThemeMode {
  return value === 'light' || value === 'dark' || value === 'system';
}

function readStoredMode(): ThemeMode {
  if (!hasStorage()) return 'system';
  const stored = localStorage.getItem(STORAGE_KEY);
  return isThemeMode(stored) ? stored : 'system';
}

class ThemeStore {
  mode = $state<ThemeMode>(readStoredMode());
  #systemPrefersDark = $state(
    hasMatchMedia() && matchMedia('(prefers-color-scheme: dark)').matches,
  );

  resolved: ResolvedTheme = $derived(
    this.mode === 'system'
      ? this.#systemPrefersDark
        ? 'dark'
        : 'light'
      : this.mode,
  );

  constructor() {
    if (!hasMatchMedia()) return;
    matchMedia('(prefers-color-scheme: dark)').addEventListener(
      'change',
      (event) => {
        this.#systemPrefersDark = event.matches;
      },
    );
  }

  cycle(): void {
    const next =
      MODE_ORDER[(MODE_ORDER.indexOf(this.mode) + 1) % MODE_ORDER.length];
    this.mode = next;
    if (hasStorage()) localStorage.setItem(STORAGE_KEY, next);
  }
}

export const theme = new ThemeStore();
