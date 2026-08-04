import { describe, expect, it } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ThemeToggle from './ThemeToggle.svelte';
import { theme } from '../theme.svelte';

describe('ThemeToggle', () => {
  it('shows the current mode label', () => {
    theme.mode = 'light';
    const { getByRole } = render(ThemeToggle);
    expect(getByRole('button')).toHaveTextContent('Light');
  });

  it('cycles the mode on click', async () => {
    theme.mode = 'light';
    const { getByRole } = render(ThemeToggle);
    const button = getByRole('button');

    await fireEvent.click(button);
    expect(button).toHaveTextContent('Dark');

    await fireEvent.click(button);
    expect(button).toHaveTextContent('Auto');
  });
});
