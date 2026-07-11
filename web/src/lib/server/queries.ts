import { getSql } from './db';
import type { EgoNetwork, EtymEdge, Lexeme, Sense } from '$lib/types';

const DEFAULT_DEPTH = 2;

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
