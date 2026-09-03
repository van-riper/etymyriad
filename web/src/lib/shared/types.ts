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
  isRedlink: boolean;
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
  | 'onomatopoeic'
  | 'surface_analysis'
  | 'inflection';

// Mirrors etl/src/etymyriad/model.py's REL_TYPE_LABELS (the canonical
// source). Rendered as an edge's <abbr title={full}>{abbr}</abbr>.
export const REL_TYPE_LABELS: Record<
  EtymRelType,
  { abbr: string; full: string }
> = {
  inherited: { abbr: 'inh.', full: 'Inherited' },
  borrowed: { abbr: 'bor.', full: 'Borrowed' },
  learned_borrowing: { abbr: 'l.bor.', full: 'Learned borrowing' },
  semi_learned_borrowing: {
    abbr: 's.l.bor.',
    full: 'Semi-learned borrowing',
  },
  derived: { abbr: 'der.', full: 'Derived' },
  root: { abbr: 'root', full: 'Root' },
  affix: { abbr: 'affix', full: 'Affix' },
  compound: { abbr: 'comp.', full: 'Compound' },
  calque: { abbr: 'calque', full: 'Calque' },
  cognate: { abbr: 'cog.', full: 'Cognate' },
  mention: { abbr: 'ment.', full: 'Mention' },
  onomatopoeic: { abbr: 'onom.', full: 'Onomatopoeic' },
  surface_analysis: { abbr: 's.a.', full: 'Surface analysis' },
  inflection: { abbr: 'infl.', full: 'Inflection' },
};

// One node in a /tree slice. depth is the signed BFS generation
// distance from the focus word: negative above (ancestors), positive
// below (descendants), 0 for the focus itself.
export interface TreeNode {
  id: string;
  langCode: string;
  headword: string;
  isReconstructed: boolean;
  isRedlink: boolean;
  depth: number;
}

// pieceOrder is the 1-based morpheme position within an affix/root/
// compound template that produced this edge (e.g. 1 for a prefix, 2
// for the root it attaches to), or null for a relType that never
// decomposes a word into ordered pieces (e.g. inherited, cognate).
export interface TreeEdge {
  srcId: string;
  dstId: string;
  relType: EtymRelType;
  sourceRef: string;
  pieceOrder?: number | null;
}

// A parent whose fan-out in one direction exceeds the server's cap:
// count is how many more children exist beyond what's already in
// `nodes`, for the "+N more" affordance. direction
// disambiguates the focus itself, which can overflow in both
// directions under the same parentId.
export interface TreeOverflow {
  parentId: string;
  direction: 'ancestor' | 'descendant';
  count: number;
}

export interface TreeSlice {
  focusId: string;
  nodes: TreeNode[];
  edges: TreeEdge[];
  overflow?: TreeOverflow[];
}
