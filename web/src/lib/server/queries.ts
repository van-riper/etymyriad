import { getSql } from './db';
import type {
  EtymEdge,
  Language,
  Lexeme,
  PositionResult,
  Sense,
  ViewportTile,
} from '$lib/types';

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

// Resolves a word to its precomputed graph position, for centering
// the viewport camera on it. Null covers both "no such lexeme" and
// "lexeme exists but has no lexeme_layout row yet" -- the two aren't
// distinguished (see ETYM-71 design doc).
//
// A lang+headword can have more than one etym_key -- true homographs
// (e.g. English "bank" the financial institution vs. the riverside),
// see ETYM-75. Pass etymKey to resolve one specific homograph; without
// it, more than one match returns `candidates` instead of a position,
// so the caller can let the user pick.
export async function lexemePosition(
  lang: string,
  headword: string,
  etymKey?: string,
): Promise<PositionResult | null> {
  const sql = await getSql();

  if (etymKey !== undefined) {
    const rows = (await sql`
			SELECT l.id, ll.x, ll.y
			FROM lexeme l
			JOIN lexeme_layout ll ON ll.lexeme_id = l.id
			WHERE l.lang_code = ${lang} AND l.headword = ${headword}
				AND l.etym_key = ${etymKey}
			LIMIT 1
		`) as Array<{ id: string; x: number; y: number }>;

    if (rows.length === 0) return null;
    return { id: rows[0].id, x: rows[0].x, y: rows[0].y };
  }

  const rows = (await sql`
		SELECT l.id, l.etym_key, ll.x, ll.y
		FROM lexeme l
		JOIN lexeme_layout ll ON ll.lexeme_id = l.id
		WHERE l.lang_code = ${lang} AND l.headword = ${headword}
		ORDER BY l.etym_key
	`) as Array<{ id: string; etym_key: string; x: number; y: number }>;

  if (rows.length === 0) return null;
  if (rows.length === 1) {
    return { id: rows[0].id, x: rows[0].x, y: rows[0].y };
  }

  const ids = rows.map((row) => row.id);
  const senseRows = (await sql`
		SELECT DISTINCT ON (lexeme_id) lexeme_id, pos, gloss
		FROM sense
		WHERE lexeme_id = ANY(${ids})
		ORDER BY lexeme_id, pos_key, gloss_key
	`) as Array<{
    lexeme_id: string;
    pos: string | null;
    gloss: string | null;
  }>;
  const senseByLexeme = new Map(senseRows.map((row) => [row.lexeme_id, row]));

  return {
    candidates: rows.map((row) => ({
      id: row.id,
      etymKey: row.etym_key,
      pos: senseByLexeme.get(row.id)?.pos ?? null,
      gloss: senseByLexeme.get(row.id)?.gloss ?? null,
    })),
  };
}

// Fetches one lexeme's attribute-tier detail (senses, source_ref,
// etc.) by id -- the lazy per-node fetch triggered by hovering or
// clicking a node in the viewport-tile structure tier.
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

// Fetch the structure tier (nodes + edges, no attribute text) inside a
// bounding box, above a degree floor. This is the whole-graph
// progressive-loading primitive: the caller only ever asks for what's
// currently on screen, never the whole table.
export async function viewportTile(
  bbox: { minX: number; minY: number; maxX: number; maxY: number },
  minDegree: number = 0,
  // ponytail: hard cap on returned nodes, ordered by proximity to the
  // box's center. DrL packs the whole 2M-lexeme graph into a compact
  // coordinate range, so a "small" box can still contain hundreds of
  // thousands of rows near the center -- this bounds render/transfer
  // cost regardless of local point density. Raise (or replace with
  // real anti-noise UX -- min-degree filtering in the UI, clustering)
  // once that work lands; it's tracked separately, not part of this
  // fix.
  limit: number = 500,
): Promise<ViewportTile> {
  const sql = await getSql();
  const centerX = (bbox.minX + bbox.maxX) / 2;
  const centerY = (bbox.minY + bbox.maxY) / 2;

  const nodeRows = (await sql`
		SELECT lexeme_id, x, y, degree
		FROM lexeme_layout
		WHERE pos <@ box(
			point(${bbox.minX}, ${bbox.minY}), point(${bbox.maxX}, ${bbox.maxY})
		) AND degree >= ${minDegree}
		ORDER BY pos <-> point(${centerX}, ${centerY})
		LIMIT ${limit}
	`) as Array<{
    lexeme_id: string;
    x: number;
    y: number;
    degree: number;
  }>;

  const ids = nodeRows.map((row) => row.lexeme_id);

  const edgeRows =
    ids.length === 0
      ? []
      : ((await sql`
			SELECT src_id, dst_id, rel_type
			FROM etymology
			WHERE src_id = ANY(${ids}) AND dst_id = ANY(${ids})
		`) as Array<{
          src_id: string;
          dst_id: string;
          rel_type: EtymEdge['relType'];
        }>);

  return {
    nodes: nodeRows.map((row) => ({
      id: row.lexeme_id,
      x: row.x,
      y: row.y,
      degree: row.degree,
    })),
    edges: edgeRows.map((row) => ({
      srcId: row.src_id,
      dstId: row.dst_id,
      relType: row.rel_type,
    })),
  };
}
