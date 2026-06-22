import { getSql } from './db';
import type { EgoNetwork, EtymEdge, Lexeme } from '$lib/types';

const DEFAULT_DEPTH = 2;

// Fetch a depth-limited neighborhood around one word, in both directions.
// This is the anti-noise primitive: the browser only ever sees this slice,
// never the whole graph.
export async function egoNetwork(
	lang: string,
	headword: string,
	depth: number = DEFAULT_DEPTH
): Promise<EgoNetwork | null> {
	const sql = getSql();

	const focus = (await sql`
		SELECT id FROM lexeme
		WHERE lang_code = ${lang} AND headword = ${headword}
		LIMIT 1
	`) as Array<{ id: number }>;

	if (focus.length === 0) return null;
	const focusId = focus[0].id;

	const edgeRows = (await sql`
		WITH RECURSIVE ego AS (
			SELECT ${focusId}::bigint AS lexeme_id, 0 AS depth
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
		src_id: number;
		dst_id: number;
		rel_type: EtymEdge['relType'];
		source_ref: string;
	}>;

	const ids = new Set<number>([focusId]);
	for (const row of edgeRows) {
		ids.add(row.src_id);
		ids.add(row.dst_id);
	}

	const nodeRows = (await sql`
		SELECT id, lang_code, headword, gloss, romanization, pos,
		       is_reconstructed, source_ref
		FROM lexeme
		WHERE id = ANY(${Array.from(ids)})
	`) as Array<{
		id: number;
		lang_code: string;
		headword: string;
		gloss: string | null;
		romanization: string | null;
		pos: string | null;
		is_reconstructed: boolean;
		source_ref: string;
	}>;

	const nodes: Lexeme[] = nodeRows.map((row) => ({
		id: row.id,
		langCode: row.lang_code,
		headword: row.headword,
		gloss: row.gloss,
		romanization: row.romanization,
		pos: row.pos,
		isReconstructed: row.is_reconstructed,
		sourceRef: row.source_ref
	}));

	const edges: EtymEdge[] = edgeRows.map((row) => ({
		srcId: row.src_id,
		dstId: row.dst_id,
		relType: row.rel_type,
		sourceRef: row.source_ref
	}));

	return { focusId, nodes, edges };
}
