import type { TreeNode } from '../../types';

// A massive tree's node-noise comes from breadth (one node with
// hundreds of children), not depth, which is already bounded
// elsewhere. Capping direct children per parent keeps layout compute
// bounded by fan-out width, not by how many nodes the slice holds
// overall, since an overflowed child's whole subtree is skipped
// rather than laid out and hidden.
//
// 10 fits comfortably across a typical desktop viewport
// (NODE_WIDTH + SIBLING_GAP px per sibling) before any horizontal
// scroll is needed to reach the "+N more" affordance.
export const MAX_SIBLINGS_PER_PARENT = 10;

export interface CoreSelection {
  coreIds: Set<string>;
  overflowByParent: Map<string, number>;
}

// BFS from the focus over this half's resolved parent/child edges,
// keeping at most MAX_SIBLINGS_PER_PARENT children per parent unless
// that parent is expanded. Kept children are the most etymologically
// relevant ones (their placing edge's rel_type priority, the same
// ranking pickParentEdges itself uses), alphabetical order only
// breaking ties within a tier, so a wide fan-out surfaces direct
// lineage over cognate/derived noise instead of an arbitrary
// alphabetical slice. An overflowed child's entire subtree is never
// visited, so the core, and therefore layoutHalf's stratify/tree call,
// stays bounded by fan-out width rather than by how many nodes this
// half holds in total.
//
// serverOverflowByParent reports children the server never fetched at
// all -- capped during the walk itself, not just at render. It adds
// to the badge count regardless of expandedParents, since "already
// showing everything present" and "more exists but hasn't been
// fetched yet" are independent facts.
export function selectCore(
  nodes: TreeNode[],
  focusId: string,
  parentIdOf: Map<string, string>,
  parentEdgeRankOf: Map<string, number>,
  expandedParents: ReadonlySet<string>,
  serverOverflowByParent: ReadonlyMap<string, number>,
): CoreSelection {
  const childrenByParent = new Map<string, TreeNode[]>();
  for (const node of nodes) {
    if (node.id === focusId) continue;
    const parentId = parentIdOf.get(node.id)!;
    const children = childrenByParent.get(parentId) ?? [];
    children.push(node);
    childrenByParent.set(parentId, children);
  }

  const coreIds = new Set<string>([focusId]);
  const overflowByParent = new Map<string, number>();
  const queue = [focusId];
  while (queue.length > 0) {
    const parentId = queue.shift()!;
    const children = childrenByParent.get(parentId) ?? [];
    children.sort((a, b) => {
      const rankDiff =
        (parentEdgeRankOf.get(a.id) ?? Infinity) -
        (parentEdgeRankOf.get(b.id) ?? Infinity);
      if (rankDiff !== 0) return rankDiff;
      return a.headword.localeCompare(b.headword, 'en');
    });
    const kept = expandedParents.has(parentId)
      ? children
      : children.slice(0, MAX_SIBLINGS_PER_PARENT);
    const overflow =
      children.length -
      kept.length +
      (serverOverflowByParent.get(parentId) ?? 0);
    if (overflow > 0) {
      overflowByParent.set(parentId, overflow);
    }
    for (const child of kept) {
      coreIds.add(child.id);
      queue.push(child.id);
    }
  }

  return { coreIds, overflowByParent };
}
