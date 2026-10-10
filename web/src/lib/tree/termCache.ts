import type { Term } from '../shared/types';

// Reopening a node's detail card reuses the first /api/terms/:id
// response instead of fetching it again.
export async function cachedTermDetail(
  cache: Map<number, Term>,
  id: number,
  fetchDetail: (id: number) => Promise<Term | null>,
): Promise<Term | null> {
  const cached = cache.get(id);
  if (cached) return cached;
  const term = await fetchDetail(id);
  if (term) cache.set(id, term);
  return term;
}
