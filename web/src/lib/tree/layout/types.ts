import type { EtymRelType, TreeNode } from '../../shared/types';

export interface PositionedNode extends TreeNode {
  x: number;
  y: number;
  isFocus: boolean;
  label: string;
  width: number;
}

export interface LayoutEdge {
  srcId: string;
  dstId: string;
  relTypes: EtymRelType[];
  sourceRefs: string[];
  kind: 'tree' | 'cross-link';
  // An SVG path `d` attribute: a curve for 'tree' edges (edgeCurve.ts),
  // or a bracket routed through the gap between rows for 'cross-link'
  // edges (crossLinkRouting.ts -- routeCrossLinks), rather than a
  // straight line that could cut through nodes it isn't connecting.
  path?: string;
  // The path's actual midpoint, for the relation-type label -- not
  // (src+dst)/2, which drifts off a curved path.
  labelPosition?: { x: number; y: number };
}

export interface ViewBox {
  minX: number;
  minY: number;
  width: number;
  height: number;
}

// A "+N more" affordance standing in for a parent's overflowed
// children. Clicking it (via an expanded parent id) reveals whatever
// is already present in `slice.nodes`; if `count` exceeds what's
// present, the rest was never fetched at all and the click must
// fetch it first -- see TreeDiagram.svelte.
export interface OverflowNode {
  parentId: string;
  direction: 'ancestor' | 'descendant';
  count: number;
  x: number;
  y: number;
  label: string;
  width: number;
}

export interface TreeLayout {
  nodes: PositionedNode[];
  edges: LayoutEdge[];
  overflow: OverflowNode[];
  viewBox: ViewBox;
}
