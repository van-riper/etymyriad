import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/svelte';
import SidePanel from './SidePanel.svelte';

function renderPanel(loading: boolean) {
  return render(SidePanel, {
    lang: 'en',
    headword: 'etymology',
    nodeCount: 0,
    focusDetail: null,
    loading,
    onsearch: vi.fn(),
    onrandom: vi.fn(),
  });
}

describe('SidePanel loading state', () => {
  it('disables search and random buttons while loading', () => {
    const { getByRole } = renderPanel(true);
    expect(getByRole('button', { name: 'Search' })).toBeDisabled();
    expect(getByRole('button', { name: 'Random' })).toBeDisabled();
  });

  it('keeps search and random buttons enabled when not loading', () => {
    const { getByRole } = renderPanel(false);
    expect(getByRole('button', { name: 'Search' })).not.toBeDisabled();
    expect(getByRole('button', { name: 'Random' })).not.toBeDisabled();
  });
});
