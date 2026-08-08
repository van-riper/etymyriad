import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/svelte';

const pageState = vi.hoisted(() => ({
  page: { status: 404, error: { message: 'No such route.' } },
}));
vi.mock('$app/state', () => pageState);

import ErrorPage from './+error.svelte';

describe('+error.svelte', () => {
  it('shows the status code and error message', () => {
    pageState.page.status = 404;
    pageState.page.error = { message: 'No such route.' };

    const { getByRole, getByText } = render(ErrorPage);

    expect(getByRole('heading', { name: '404' })).toBeInTheDocument();
    expect(getByText('No such route.')).toBeInTheDocument();
  });

  it('falls back to a generic message when the error has none', () => {
    pageState.page.status = 500;
    // @ts-expect-error -- exercising the missing-error fallback path
    pageState.page.error = null;

    const { getByRole, getByText } = render(ErrorPage);

    expect(getByRole('heading', { name: '500' })).toBeInTheDocument();
    expect(getByText('Something went wrong.')).toBeInTheDocument();
  });
});
