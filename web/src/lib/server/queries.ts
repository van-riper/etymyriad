import { getSql } from './db';
import type { Language, Lexeme, Sense } from '$lib/types';

// Picks one lexeme uniformly at random, for the "random word" button.
// Restricted to langCode when given, otherwise any language.
export async function randomLexeme(langCode?: string): Promise<{
  langCode: string;
  headword: string;
} | null> {
  const sql = await getSql();
  // ponytail: ORDER BY random() full-scans+sorts ~2M rows (~500ms locally).
  // Fine for a manually-triggered button; switch to TABLESAMPLE or a
  // precomputed random offset if this becomes a hot path.
  const rows = (await sql`
		SELECT lang_code, headword FROM lexeme
		WHERE ${langCode ?? null}::text IS NULL OR lang_code = ${langCode ?? null}
		ORDER BY random() LIMIT 1
	`) as Array<{ lang_code: string; headword: string }>;

  if (rows.length === 0) return null;
  return { langCode: rows[0].lang_code, headword: rows[0].headword };
}

// Fetches every language's code/name, for the client-side language
// typeahead (ETYM-85). ~2k rows, small enough to ship whole and rank
// in the browser rather than round-tripping per keystroke. Excludes
// ETYM-84's comma-joined alias codes (a data bug, out of scope here)
// so they don't surface as bogus suggestions.
export async function languageList(): Promise<Language[]> {
  const sql = await getSql();

  const rows = (await sql`
		SELECT code, name FROM language
		WHERE code NOT LIKE '%,%'
		ORDER BY code
	`) as Array<{ code: string; name: string }>;

  return rows;
}

// Fetches one lexeme's attribute-tier detail (senses, source_ref,
// etc.) by id -- the lazy per-node fetch triggered by hovering or
// clicking a node.
export async function lexemeDetail(id: string): Promise<Lexeme | null> {
  const sql = await getSql();

  const rows = (await sql`
		SELECT l.id, l.lang_code, lang.name AS lang_name, l.headword,
		       l.etymology_number, l.romanization, l.is_reconstructed,
		       l.source_ref
		FROM lexeme l
		JOIN language lang ON lang.code = l.lang_code
		WHERE l.id = ${id}
		LIMIT 1
	`) as Array<{
    id: string;
    lang_code: string;
    lang_name: string;
    headword: string;
    etymology_number: string | null;
    romanization: string | null;
    is_reconstructed: boolean;
    source_ref: string;
  }>;

  if (rows.length === 0) return null;
  const row = rows[0];

  const senseRows = (await sql`
		SELECT pos, gloss, source_ref
		FROM sense
		WHERE lexeme_id = ${id}
	`) as Array<{
    pos: string | null;
    gloss: string | null;
    source_ref: string;
  }>;

  const senses: Sense[] = senseRows.map((s) => ({
    pos: s.pos,
    gloss: s.gloss,
    sourceRef: s.source_ref,
  }));

  return {
    id: row.id,
    langCode: row.lang_code,
    langName: row.lang_name,
    headword: row.headword,
    etymologyNumber: row.etymology_number,
    romanization: row.romanization,
    isReconstructed: row.is_reconstructed,
    sourceRef: row.source_ref,
    senses,
  };
}
