import { stratify, tree as d3tree } from 'd3-hierarchy';
import type { TreeNode } from '../../shared/types';
import {
  cardHeight,
  composeLabel,
  MARKER_HEIGHT,
  NODE_WIDTH,
} from './nodeMetrics';
import type { CoreSelection } from './coreSelection';
import type { OverflowNode } from './types';

const SIBLING_GAP = 24;
// The gap between the tallest cards of adjacent generations. The room
// gives each tree edge's bezier curve (edgeCurve.ts) vertical space to
// bend through before it has to straighten out for its node, so a
// wide sibling fan-out doesn't compress that bend into a visibly
// deformed kink.
const ROW_GAP = 48;

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
  height: number;
}

// Omits `direction`, which the caller only knows once both halves
// have been laid out (see layoutTree).
type UndirectedOverflow = Omit<OverflowNode, 'direction'>;

interface PositionedDatum {
  x: number;
  y: number;
  label: string;
  height: number;
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
        height: cardHeight(node),
      };
    });
  for (const [parentId, count] of core.overflowByParent) {
    data.push({
      id: `${parentId}${OVERFLOW_ID_SUFFIX}`,
      parentId: String(parentId),
      nodeId: null,
      parentNodeId: parentId,
      headword: '',
      isOverflow: true,
      pieceOrder: null,
      label: `+${count} more`,
      height: MARKER_HEIGHT,
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
  const positionedRoot = d3tree<StratifyDatum>().nodeSize([
    NODE_WIDTH + SIBLING_GAP,
    1,
  ])(root);

  // d3 spaces rows evenly, but card heights vary, so each row sits
  // far enough from the one before it to clear both rows' tallest
  // cards.
  const rowHeights: number[] = [];
  for (const node of positionedRoot.descendants()) {
    rowHeights[node.depth] = Math.max(
      rowHeights[node.depth] ?? 0,
      node.data.height,
    );
  }
  const rowY = [0];
  for (let depth = 1; depth < rowHeights.length; depth++) {
    rowY[depth] =
      rowY[depth - 1] +
      rowHeights[depth - 1] / 2 +
      ROW_GAP +
      rowHeights[depth] / 2;
  }

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
        y: rowY[node.depth],
        label: node.data.label,
      });
    } else {
      positions.set(node.data.nodeId!, {
        x,
        y: rowY[node.depth],
        label: node.data.label,
        height: node.data.height,
      });
    }
  }
  return { positions, overflow };
}
