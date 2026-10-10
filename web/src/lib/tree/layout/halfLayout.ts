import { stratify, tree as d3tree } from 'd3-hierarchy';
import type { TreeNode } from '../../shared/types';
import { composeLabel, widthForLabel } from './nodeMetrics';
import type { CoreSelection } from './coreSelection';
import type { OverflowNode } from './types';

const SIBLING_GAP = 24;
// The gap between generations. Wider than a tight fixed-width tree
// needs on its own: the extra room gives each tree edge's bezier
// curve (edgeCurve.ts) more vertical space to bend through before it
// has to straighten out for its node, so a wide sibling fan-out
// doesn't compress that bend into a visibly deformed kink.
const ROW_HEIGHT = 80;

const OVERFLOW_ID_SUFFIX = '::overflow';

interface StratifyDatum {
  id: string;
  parentId: string | null;
  nodeId: number | null;
  parentNodeId: number | null;
  headword: string;
  isOverflow: boolean;
  pieceOrder: number | null;
  label: string;
  width: number;
}

// Omits `direction`, which the caller only knows once both halves
// have been laid out (see layoutTree).
type UndirectedOverflow = Omit<OverflowNode, 'direction'>;

interface PositionedDatum {
  x: number;
  y: number;
  label: string;
  width: number;
}

export interface HalfLayout {
  positions: Map<number, PositionedDatum>;
  overflow: UndirectedOverflow[];
}

// Lays out one half (every node with depth <= 0, or depth >= 0) as a
// strict tree rooted at the focus, then recenters it so the focus
// sits at x = 0: d3.tree() centers a root over its own children,
// not necessarily at x = 0, and both halves must agree on where the
// shared focus sits. Only the core selected above is fed to
// stratify/tree; a "+N more" marker takes each overflowed parent's
// place as one extra child, so d3 reserves it a slot the same way it
// would a real sibling.
export function layoutHalf(
  nodes: TreeNode[],
  focusId: number,
  parentIdOf: Map<number, number>,
  parentEdgePieceOrderOf: Map<number, number | null>,
  core: CoreSelection,
): HalfLayout {
  const data: StratifyDatum[] = nodes
    .filter((node) => core.coreIds.has(node.id))
    .map((node) => {
      const label = composeLabel(node);
      return {
        id: String(node.id),
        parentId: node.id === focusId ? null : String(parentIdOf.get(node.id)!),
        nodeId: node.id,
        parentNodeId: node.id === focusId ? null : parentIdOf.get(node.id)!,
        headword: node.headword,
        isOverflow: false,
        pieceOrder: parentEdgePieceOrderOf.get(node.id) ?? null,
        label,
        width: widthForLabel(label),
      };
    });
  for (const [parentId, count] of core.overflowByParent) {
    const label = `+${count} more`;
    data.push({
      id: `${parentId}${OVERFLOW_ID_SUFFIX}`,
      parentId: String(parentId),
      nodeId: null,
      parentNodeId: parentId,
      headword: '',
      isOverflow: true,
      pieceOrder: null,
      label,
      width: widthForLabel(label),
    });
  }

  const root = stratify<StratifyDatum>()
    .id((d) => d.id)
    .parentId((d) => d.parentId)(data);

  root.sort((a, b) => {
    // An overflow marker isn't a real headword, so it always sorts
    // after its parent's real (kept) children, however they collate.
    if (a.data.isOverflow) return 1;
    if (b.data.isOverflow) return -1;
    // Siblings that are composition pieces of their shared parent (a
    // prefix/root/suffix decomposition) order the way they occur in
    // that word, not alphabetically, grouped ahead of any sibling
    // that isn't a piece at all (e.g. an inherited lineage
    // edge to the same parent), rather than interleaving by headword,
    // since comparing a piece to a non-piece by headword alone isn't
    // transitive and can silently reorder two pieces relative to each
    // other depending on where a third, unrelated sibling falls.
    //
    // A piece whose headword carries a leading dash is Wiktionary's
    // own convention for "this is a suffix" (see `_add_affix_dash` in
    // the ETL): it attaches after a base, so it sorts after non-piece
    // siblings instead. This matters when the base itself isn't a
    // piece of the same decomposition at all -- e.g. a single-argument
    // {{af|de|-isch}} call, whose one term gets piece_order 1 simply
    // for being the lone slot, while its real base is asserted via a
    // separate, non-piece bor/der edge.
    const orderA = a.data.pieceOrder;
    const orderB = b.data.pieceOrder;
    const isSuffixPiece = (d: StratifyDatum) =>
      d.pieceOrder != null && d.headword.startsWith('-');
    if (orderA == null && orderB != null) {
      return isSuffixPiece(b.data) ? -1 : 1;
    }
    if (orderA != null && orderB == null) {
      return isSuffixPiece(a.data) ? 1 : -1;
    }
    if (orderA != null && orderB != null && orderA !== orderB) {
      return orderA - orderB;
    }
    return a.data.headword.localeCompare(b.data.headword, 'en');
  });
  // nodeSize's x-unit is 1, so separation()'s return value is read
  // directly as the pixel gap between adjacent node centers, letting
  // it vary per node pair instead of the fixed NODE_WIDTH + SIBLING_GAP
  // this replaces. The (avgWidth + GAP) * multiplier shape (not just
  // multiplying the gap) is what preserves the old fixed-width
  // spacing exactly when both nodes sit at the floor width: d3's old
  // default separation (1 for siblings, 2 for cousins) times the old
  // nodeSize[0] gave 144/288 at the floor; this formula gives the same
  // 144/288 there, and now scales with each node's own width beyond it.
  const positionedRoot = d3tree<StratifyDatum>()
    .nodeSize([1, ROW_HEIGHT])
    .separation((a, b) => {
      const avgWidth = (a.data.width + b.data.width) / 2;
      const multiplier = a.parent === b.parent ? 1 : 2;
      return (avgWidth + SIBLING_GAP) * multiplier;
    })(root);

  const offsetX = positionedRoot.x;
  const positions = new Map<number, PositionedDatum>();
  const overflow: UndirectedOverflow[] = [];
  for (const node of positionedRoot.descendants()) {
    const x = node.x - offsetX;
    if (node.data.isOverflow) {
      const parentId = node.data.parentNodeId!;
      overflow.push({
        parentId,
        count: core.overflowByParent.get(parentId)!,
        x,
        y: node.y,
        label: node.data.label,
        width: node.data.width,
      });
    } else {
      positions.set(node.data.nodeId!, {
        x,
        y: node.y,
        label: node.data.label,
        width: node.data.width,
      });
    }
  }
  return { positions, overflow };
}
