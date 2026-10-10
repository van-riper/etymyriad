// Shared graph types. These mirror db/schema.sql and are used by both the
// server routes (API) and the Svelte components (UI).

export interface Language {
  code: string;
  name: string;
}

export interface Sense {
  section: number;
  partOfSpeech: string | null;
  gloss: string | null;
}

export interface Term {
  id: number;
  langCode: string;
  langName: string;
  headword: string;
  isReconstructed: boolean;
  isRedlink: boolean;
  sourceRef: string;
  senses: Sense[];
}

// One section of a (lang, headword) lookup. A homograph term returns
// one summary per section, for a disambiguation picker.
export interface TermSummary {
  id: number;
  section: number;
  partOfSpeech: string | null;
  gloss: string | null;
}

// Mirrors db/schema.sql's edge_type enum.
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
  | 'mention'
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
  mention: { abbr: 'ment.', full: 'Mention' },
  surface_analysis: { abbr: 's.a.', full: 'Surface analysis' },
  inflection: { abbr: 'infl.', full: 'Inflection' },
};

// One node in a /tree slice. depth is the signed BFS generation
// distance from the focus word: negative above (ancestors), positive
// below (descendants), 0 for the focus itself.
export interface TreeNode {
  id: number;
  langCode: string;
  headword: string;
  isReconstructed: boolean;
  isRedlink: boolean;
  depth: number;
}

// pieceOrder is the 1-based morpheme position within an affix/root/
// compound template that produced this edge (e.g. 1 for a prefix, 2
// for the root it attaches to), or null for a relType that never
// decomposes a word into ordered pieces (e.g. inherited).
export interface TreeEdge {
  srcId: number;
  dstId: number;
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
  parentId: number;
  direction: 'ancestor' | 'descendant';
  count: number;
}

// section is the focus's "Etymology N" the slice was walked with
// (absent or 0 = every section).
export interface TreeSlice {
  focusId: number;
  section?: number;
  nodes: TreeNode[];
  edges: TreeEdge[];
  overflow?: TreeOverflow[];
}
