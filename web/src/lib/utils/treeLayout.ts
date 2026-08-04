import type { EtymRelType, TreeNode, TreeSlice } from '../types';

export const NODE_WIDTH = 120;
export const NODE_HEIGHT = 32;

const PADDING = 16;

export interface PositionedNode extends TreeNode {
  x: number;
  y: number;
  isFocus: boolean;
}

export interface LayoutEdge {
  srcId: string;
  dstId: string;
  relTypes: EtymRelType[];
  sourceRefs: string[];
  kind: 'tree' | 'cross-link';
}

export interface ViewBox {
  minX: number;
  minY: number;
  width: number;
  height: number;
}

export interface TreeLayout {
  nodes: PositionedNode[];
  edges: LayoutEdge[];
  viewBox: ViewBox;
}

export function layoutTree(slice: TreeSlice): TreeLayout {
  const focus = slice.nodes.find((n) => n.id === slice.focusId)!;
  const node: PositionedNode = { ...focus, x: 0, y: 0, isFocus: true };

  return {
    nodes: [node],
    edges: [],
    viewBox: {
      minX: -NODE_WIDTH / 2 - PADDING,
      minY: -NODE_HEIGHT / 2 - PADDING,
      width: NODE_WIDTH + PADDING * 2,
      height: NODE_HEIGHT + PADDING * 2,
    },
  };
}
