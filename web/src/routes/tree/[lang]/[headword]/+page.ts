import type { PageLoad } from './$types';
import type { Lexeme, LexemeSummary, TreeSlice } from '$lib/types';

export const load: PageLoad = async ({ params, url, fetch }) => {
  const etym = url.searchParams.get('etym') ?? undefined;
  const qs = new URLSearchParams({
    lang: params.lang,
    headword: params.headword,
  });
  if (etym) qs.set('etym', etym);

  const matches: LexemeSummary[] = await (
    await fetch(`/api/lexemes?${qs}`)
  ).json();

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
    fetch(`/api/trees/${matches[0].id}`).then((r) => r.json()),
    fetch(`/api/lexemes/${matches[0].id}`).then((r) => r.json()),
  ]);
  return {
    status: 'tree' as const,
    lang: params.lang,
    headword: params.headword,
    slice,
    focusDetail,
  };
};
