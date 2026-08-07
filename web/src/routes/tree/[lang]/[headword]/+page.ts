import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { Lexeme, LexemeSummary, TreeSlice } from '$lib/types';
import { apiFetch } from '$lib/utils/apiFetch';

export const load: PageLoad = async ({ params, url, fetch }) => {
  const etym = url.searchParams.get('etym') ?? undefined;
  const qs = new URLSearchParams({
    lang: params.lang,
    headword: params.headword,
  });
  if (etym) qs.set('etym', etym);

  const lexemesRes = await apiFetch(`/api/lexemes?${qs}`, fetch);
  if (!lexemesRes.ok) {
    const body = (await lexemesRes.json().catch(() => null)) as {
      message?: string;
    } | null;
    throw error(lexemesRes.status, body?.message ?? 'Request failed');
  }
  const matches: LexemeSummary[] = await lexemesRes.json();

  if (matches.length === 0) {
    return {
      status: 'notfound' as const,
      lang: params.lang,
      headword: params.headword,
    };
  }
  if (matches.length > 1) {
    return {
      status: 'homograph' as const,
      lang: params.lang,
      headword: params.headword,
      candidates: matches,
    };
  }

  const [slice, focusDetail]: [TreeSlice, Lexeme] = await Promise.all([
    apiFetch(`/api/trees/${matches[0].id}`, fetch).then((r) => r.json()),
    apiFetch(`/api/lexemes/${matches[0].id}`, fetch).then((r) => r.json()),
  ]);
  return {
    status: 'tree' as const,
    lang: params.lang,
    headword: params.headword,
    slice,
    focusDetail,
  };
};
