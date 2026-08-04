// Shared graph types. These mirror db/schema.sql and are used by both the
// server routes (API) and the Svelte components (UI).

export interface Language {
  code: string;
  name: string;
}

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

// One match for a (lang, headword) lookup. A unique match is a
// single-element array; a homograph (more than one etym_key) is an
// array of one summary per candidate, for a disambiguation picker.
export interface LexemeSummary {
  id: string;
  etymKey: string;
  pos: string | null;
  gloss: string | null;
}

// Mirrors db/schema.sql's etym_rel_type enum.
export type EtymRelType =
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

// One node in a /tree slice. depth is the signed BFS generation
// distance from the focus word: negative above (ancestors), positive
// below (descendants), 0 for the focus itself.
export interface TreeNode {
  id: string;
  langCode: string;
  headword: string;
  depth: number;
}

export interface TreeEdge {
  srcId: string;
  dstId: string;
  relType: EtymRelType;
  sourceRef: string;
}

export interface TreeSlice {
  focusId: string;
  nodes: TreeNode[];
  edges: TreeEdge[];
}
