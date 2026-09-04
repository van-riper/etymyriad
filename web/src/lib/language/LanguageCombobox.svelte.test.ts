import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import LanguageCombobox from './LanguageCombobox.svelte';
import type { Language } from '../shared/types';

const languages: Language[] = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  { code: 'eo', name: 'Esperanto' },
];

function stubLanguagesFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ ok: true, json: async () => languages })),
  );
}

async function renderReady(props: { value: string; placeholder?: string }) {
  stubLanguagesFetch();
  const result = render(LanguageCombobox, props);
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  return result;
}

describe('LanguageCombobox', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows no suggestions until the user types', async () => {
    const { queryByRole } = await renderReady({ value: '' });

    expect(queryByRole('option')).not.toBeInTheDocument();
  });

  it('suggests matches ranked by rankLanguages as the user types', async () => {
    const { getByLabelText, findByRole, queryByRole } = await renderReady({
      value: '',
    });

    await fireEvent.input(getByLabelText('Language code'), {
      target: { value: 'es' },
    });

    expect(await findByRole('option', { name: /Spanish/i })).toBeVisible();
    expect(queryByRole('option', { name: /English/i })).not.toBeInTheDocument();
  });

  it('reflects what the user types in the input', async () => {
    const { getByLabelText } = await renderReady({ value: '' });

    const input = getByLabelText('Language code') as HTMLInputElement;
    await fireEvent.input(input, { target: { value: 'es' } });

    expect(input.value).toBe('es');
  });

  it('selects a suggestion on click, updating the input value', async () => {
    const { getByLabelText, findByRole } = await renderReady({ value: '' });

    const input = getByLabelText('Language code') as HTMLInputElement;
    await fireEvent.input(input, { target: { value: 'es' } });

    const option = await findByRole('option', { name: /Spanish/i });
    await fireEvent.click(option);

    expect(input.value).toBe('es');
  });

  it('closes the suggestion list on Escape', async () => {
    const { getByLabelText, findByRole, queryByRole } = await renderReady({
      value: '',
    });

    const input = getByLabelText('Language code');
    await fireEvent.input(input, { target: { value: 'es' } });
    await findByRole('option', { name: /Spanish/i });

    await fireEvent.keyDown(input, { key: 'Escape' });

    await waitFor(() => expect(queryByRole('option')).not.toBeInTheDocument());
  });

  it('has a visible label associated with the input', async () => {
    const { getByText, getByLabelText } = await renderReady({ value: '' });

    const label = getByText('Language code', { selector: 'label' });
    expect(label).toBeVisible();
    const input = getByLabelText('Language code') as HTMLInputElement;
    expect(label.getAttribute('for')).toBe(input.id);
  });

  it('shows the placeholder rather than a bound value when empty', async () => {
    const { getByLabelText } = await renderReady({
      value: '',
      placeholder: 'en',
    });

    expect(getByLabelText('Language code')).toHaveAttribute(
      'placeholder',
      'en',
    );
  });

  it('displays an externally-changed value, e.g. after navigation', async () => {
    const { getByLabelText, rerender } = await renderReady({ value: 'en' });

    const input = getByLabelText('Language code') as HTMLInputElement;
    expect(input.value).toBe('en');

    await rerender({ value: 'de' });

    expect(input.value).toBe('de');
  });
});
