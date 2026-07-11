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
  id: number;
  langCode: string;
  headword: string;
  etymologyNumber: string | null;
  romanization: string | null;
  isReconstructed: boolean;
  sourceRef: string;
  senses: Sense[];
}

export interface EtymEdge {
  srcId: number;
  dstId: number;
  relType: RelType;
  sourceRef: string;
}

// A focused slice of the graph around one word (the anti-noise primitive).
export interface EgoNetwork {
  focusId: number;
  nodes: Lexeme[];
  edges: EtymEdge[];
}
