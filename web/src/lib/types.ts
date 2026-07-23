// Shared graph types. These mirror db/schema.sql and are used by both the
// server routes (API) and the Svelte components (UI).

export type RelType =
  | 'inherited'
  | 'borrowed'
  | 'learned_borrowing'
  | 'semi_learned_borrowing'
  | 'derived'
  | 'root'
  | 'affix'
  | 'compound'
  | 'calque'
  | 'cognate'
  | 'mention'
  | 'onomatopoeic';

export interface Sense {
  pos: string | null;
  gloss: string | null;
  sourceRef: string;
}

export interface Lexeme {
  id: string;
  langCode: string;
  langName: string;
  headword: string;
  etymologyNumber: string | null;
  romanization: string | null;
  isReconstructed: boolean;
  sourceRef: string;
  senses: Sense[];
}

export interface EtymEdge {
  srcId: string;
  dstId: string;
  relType: RelType;
  sourceRef: string;
}

// Structure tier for whole-graph viewport queries: position + degree
// only, no headword/gloss/source text -- that loads lazily per-node
// on click/hover (see ETYM-57's structure/attribute split), not here.
export interface LayoutNode {
  id: string;
  x: number;
  y: number;
  degree: number;
}

export interface LayoutEdge {
  srcId: string;
  dstId: string;
  relType: RelType;
}

export interface ViewportTile {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
}
