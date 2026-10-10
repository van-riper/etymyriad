import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { Term, TermSummary, TreeSlice } from '$lib/shared/types';
import { apiFetch } from '$lib/shared/apiFetch';
import { parseSection } from '$lib/shared/validation';

export const load: PageLoad = async ({ params, url, fetch }) => {
  const section = parseSection(url.searchParams.get('etym'));
  if (section === null) throw error(400, 'etym must be 0 to 32767');
  const qs = new URLSearchParams({
    lang: params.lang,
    headword: params.headword,
  });
  if (url.searchParams.has('etym')) qs.set('section', String(section));

  const termsRes = await apiFetch(`/api/terms?${qs}`, fetch);
  if (!termsRes.ok) {
    const body = (await termsRes.json().catch(() => null)) as {
      message?: string;
    } | null;
    throw error(termsRes.status, body?.message ?? 'Request failed');
  }
  const matches: TermSummary[] = await termsRes.json();

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
