import { getSql } from './db';
import type {
  EgoNetwork,
  EtymEdge,
  Lexeme,
  Sense,
  ViewportTile,
} from '$lib/types';

const DEFAULT_DEPTH = 2;

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

// Resolves a word to its precomputed graph position, for centering
// the viewport camera on it. Null covers both "no such lexeme" and
// "lexeme exists but has no lexeme_layout row yet" -- the two aren't
// distinguished (see ETYM-71 design doc).
export async function lexemePosition(
  lang: string,
  headword: string,
): Promise<{ id: string; x: number; y: number } | null> {
  const sql = await getSql();

  const rows = (await sql`
		SELECT l.id, ll.x, ll.y
		FROM lexeme l
		JOIN lexeme_layout ll ON ll.lexeme_id = l.id
		WHERE l.lang_code = ${lang} AND l.headword = ${headword}
		LIMIT 1
	`) as Array<{ id: string; x: number; y: number }>;

  if (rows.length === 0) return null;
  return { id: rows[0].id, x: rows[0].x, y: rows[0].y };
}

// Fetch a depth-limited neighborhood around one word, in both directions.
// This is the anti-noise primitive: the browser only ever sees this slice,
// never the whole graph.
export async function egoNetwork(
  lang: string,
  headword: string,
  depth: number = DEFAULT_DEPTH,
): Promise<EgoNetwork | null> {
  const sql = await getSql();

  const focus = (await sql`
		SELECT id FROM lexeme
		WHERE lang_code = ${lang} AND headword = ${headword}
		LIMIT 1
	`) as Array<{ id: string }>;

  if (focus.length === 0) return null;
  const focusId = focus[0].id;

  const edgeRows = (await sql`
		WITH RECURSIVE ego AS (
			SELECT ${focusId}::uuid AS lexeme_id, 0 AS depth
			UNION
			SELECT CASE WHEN e.src_id = g.lexeme_id THEN e.dst_id ELSE e.src_id END,
			       g.depth + 1
			FROM ego g
			JOIN etymology e ON g.lexeme_id IN (e.src_id, e.dst_id)
			WHERE g.depth < ${depth}
		)
		SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref
		FROM etymology e
		WHERE e.src_id IN (SELECT lexeme_id FROM ego)
		  AND e.dst_id IN (SELECT lexeme_id FROM ego)
	`) as Array<{
    src_id: string;
    dst_id: string;
    rel_type: EtymEdge['relType'];
    source_ref: string;
  }>;

  const ids = new Set<string>([focusId]);
  for (const row of edgeRows) {
    ids.add(row.src_id);
    ids.add(row.dst_id);
  }

  const nodeRows = (await sql`
		SELECT id, lang_code, headword, etymology_number, romanization,
		       is_reconstructed, source_ref
		FROM lexeme
		WHERE id = ANY(${Array.from(ids)})
	`) as Array<{
    id: string;
    lang_code: string;
    headword: string;
    etymology_number: string | null;
    romanization: string | null;
    is_reconstructed: boolean;
    source_ref: string;
  }>;

  const senseRows = (await sql`
		SELECT lexeme_id, pos, gloss, source_ref
		FROM sense
		WHERE lexeme_id = ANY(${Array.from(ids)})
	`) as Array<{
    lexeme_id: string;
    pos: string | null;
    gloss: string | null;
    source_ref: string;
  }>;

  const sensesByLexeme = new Map<string, Sense[]>();
  for (const row of senseRows) {
    const senses = sensesByLexeme.get(row.lexeme_id) ?? [];
    senses.push({
      pos: row.pos,
      gloss: row.gloss,
      sourceRef: row.source_ref,
    });
    sensesByLexeme.set(row.lexeme_id, senses);
  }

  const nodes: Lexeme[] = nodeRows.map((row) => ({
    id: row.id,
    langCode: row.lang_code,
    headword: row.headword,
    etymologyNumber: row.etymology_number,
    romanization: row.romanization,
    isReconstructed: row.is_reconstructed,
    sourceRef: row.source_ref,
    senses: sensesByLexeme.get(row.id) ?? [],
  }));

  const edges: EtymEdge[] = edgeRows.map((row) => ({
    srcId: row.src_id,
    dstId: row.dst_id,
    relType: row.rel_type,
    sourceRef: row.source_ref,
  }));

  return { focusId, nodes, edges };
}

// Fetch the structure tier (nodes + edges, no attribute text) inside a
// bounding box, above a degree floor. This is the whole-graph
// progressive-loading primitive: the caller only ever asks for what's
// currently on screen, never the whole table.
export async function viewportTile(
  bbox: { minX: number; minY: number; maxX: number; maxY: number },
  minDegree: number = 0,
): Promise<ViewportTile> {
  const sql = await getSql();

  const nodeRows = (await sql`
		SELECT lexeme_id, x, y, degree
		FROM lexeme_layout
		WHERE pos <@ box(
			point(${bbox.minX}, ${bbox.minY}), point(${bbox.maxX}, ${bbox.maxY})
		) AND degree >= ${minDegree}
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
