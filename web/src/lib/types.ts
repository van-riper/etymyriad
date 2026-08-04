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
