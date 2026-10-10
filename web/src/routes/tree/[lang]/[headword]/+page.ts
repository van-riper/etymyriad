import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { Term, TermSummary, TreeSlice } from '$lib/shared/types';
import { apiFetch } from '$lib/shared/apiFetch';
import { parseSection } from '$lib/shared/validation';

async function fetchMatches(
  fetch: typeof globalThis.fetch,
  lang: string,
  headword: string,
  section: number | null,
): Promise<TermSummary[]> {
  const qs = new URLSearchParams({ lang, headword });
  if (section !== null) qs.set('section', String(section));
  const termsRes = await apiFetch(`/api/terms?${qs}`, fetch);
  if (!termsRes.ok) {
    const body = (await termsRes.json().catch(() => null)) as {
      message?: string;
    } | null;
    throw error(termsRes.status, body?.message ?? 'Request failed');
  }
  return termsRes.json();
}

export const load: PageLoad = async ({ params, url, fetch }) => {
  // Old shared links carry an empty or non-numeric etym; treat it as
  // absent, and a section the term lacks as no filter at all.
  const etym = url.searchParams.get('etym');
  const section = etym === null ? null : parseSection(etym);
  let matches = await fetchMatches(
    fetch,
    params.lang,
    params.headword,
    section,
  );
  if (matches.length === 0 && section !== null) {
    matches = await fetchMatches(fetch, params.lang, params.headword, null);
  }

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

  const [match] = matches;
  const [slice, focusDetail]: [TreeSlice, Term] = await Promise.all([
    apiFetch(`/api/trees/${match.id}?section=${match.section}`, fetch).then(
      (r) => r.json(),
    ),
    apiFetch(`/api/terms/${match.id}`, fetch).then((r) => r.json()),
  ]);
  return {
    status: 'tree' as const,
    lang: params.lang,
    headword: params.headword,
    slice,
    focusDetail,
  };
};
