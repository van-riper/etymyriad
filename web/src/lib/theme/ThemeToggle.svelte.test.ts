import { describe, expect, it } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ThemeToggle from './ThemeToggle.svelte';
import { theme } from './store.svelte';

describe('ThemeToggle', () => {
  it('shows a sun icon for light mode', () => {
    theme.mode = 'light';
    const { getByTestId } = render(ThemeToggle);
    expect(getByTestId('icon-sun')).toBeTruthy();
  });

  it('shows a moon icon for dark mode', () => {
    theme.mode = 'dark';
    const { getByTestId } = render(ThemeToggle);
    expect(getByTestId('icon-moon')).toBeTruthy();
  });

  it('shows an auto icon for system mode', () => {
    theme.mode = 'system';
    const { getByTestId } = render(ThemeToggle);
    expect(getByTestId('icon-auto')).toBeTruthy();
  });

  it('cycles the mode on click', async () => {
    theme.mode = 'light';
    const { getByRole, getByTestId } = render(ThemeToggle);
    const button = getByRole('button');

    await fireEvent.click(button);
    expect(getByTestId('icon-moon')).toBeTruthy();

    await fireEvent.click(button);
    expect(getByTestId('icon-auto')).toBeTruthy();
  });
});
