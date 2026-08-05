import { getSql } from './db';
import type {
  EtymRelType,
  Language,
  Lexeme,
  LexemeSummary,
  Sense,
  TreeEdge,
  TreeSlice,
} from '$lib/types';

// /tree has no UI-driven way to change this yet -- raise it if a
// deeper genealogy view turns out to be wanted.
const DEFAULT_TREE_DEPTH = 5;

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

// Resolves a (lang, headword) pair to its lexeme(s), for /tree's focus
// word lookup (ETYM-113). A lang+headword can have more than one
// etym_key -- true homographs (e.g. English "bank" the financial
// institution vs. the riverside) -- see ETYM-75. Pass etymKey to
// narrow to one specific homograph; without it, more than one match
// returns every candidate so the caller can offer a picker. A unique
// match is a single-element array either way.
export async function lexemesByHeadword(
  lang: string,
  headword: string,
  etymKey?: string,
): Promise<LexemeSummary[]> {
  const sql = await getSql();

  const rows = (await sql`
		SELECT id, etym_key FROM lexeme
		WHERE lang_code = ${lang} AND headword = ${headword}
			AND (${etymKey ?? null}::text IS NULL OR etym_key = ${etymKey ?? null})
		ORDER BY etym_key
	`) as Array<{ id: string; etym_key: string }>;

  if (rows.length === 0) return [];

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

  const summarize = (row: { id: string; etym_key: string }): LexemeSummary => ({
    id: row.id,
    etymKey: row.etym_key,
    pos: senseByLexeme.get(row.id)?.pos ?? null,
    gloss: senseByLexeme.get(row.id)?.gloss ?? null,
  });

  if (rows.length === 1) return [summarize(rows[0])];

  // A lexeme with no sense row at all is a same-language bound-morpheme
  // reference that couldn't be merged into its real numbered entry
  // because more than one exists (an unresolvable ambiguity, not a
  // homograph) -- never worth offering as a pick, since it carries no
  // gloss/pos to tell it apart by.
  const realRows = rows.filter((row) => senseByLexeme.has(row.id));
  return realRows.length === 1
    ? [summarize(realRows[0])]
    : realRows.map(summarize);
}

// Bounded bidirectional BFS from a focus lexeme: every ancestor and
// descendant up to maxDepth hops, each tagged with its signed BFS
// generation distance from the focus (negative = ancestor, positive =
// descendant, 0 = the focus itself). Powers /tree's genealogy view --
// supersedes viewportTile's spatial-box slice entirely, since /tree has
// no notion of (x, y).
export async function treeSlice(
  focusId: string,
  maxDepth: number = DEFAULT_TREE_DEPTH,
): Promise<TreeSlice | null> {
  const sql = await getSql();
  const minDepth = -maxDepth;

  const edgeRows = (await sql`
		WITH RECURSIVE ancestors AS (
			SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref, -1 AS depth
			FROM etymology e WHERE e.dst_id = ${focusId}
			UNION ALL
			SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref, a.depth - 1
			FROM etymology e JOIN ancestors a ON e.dst_id = a.src_id
			WHERE a.depth > ${minDepth}
		),
		descendants AS (
			SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref, 1 AS depth
			FROM etymology e WHERE e.src_id = ${focusId}
			UNION ALL
			SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref, d.depth + 1
			FROM etymology e JOIN descendants d ON e.src_id = d.dst_id
			WHERE d.depth < ${maxDepth}
		)
		SELECT * FROM ancestors
		UNION ALL
		SELECT * FROM descendants
	`) as Array<{
    src_id: string;
    dst_id: string;
    rel_type: EtymRelType;
    source_ref: string;
    depth: number;
  }>;

  // A DAG (not a strict tree) can reach the same node via more than one
  // path at different depths -- keep the shortest, matching BFS.
  const nodeDepth = new Map<string, number>([[focusId, 0]]);
  const edgeByKey = new Map<string, TreeEdge>();
  for (const row of edgeRows) {
    const farId = row.depth < 0 ? row.src_id : row.dst_id;
    const known = nodeDepth.get(farId);
    if (known === undefined || Math.abs(row.depth) < Math.abs(known)) {
      nodeDepth.set(farId, row.depth);
    }
    edgeByKey.set(`${row.src_id}:${row.dst_id}:${row.rel_type}`, {
      srcId: row.src_id,
      dstId: row.dst_id,
      relType: row.rel_type,
      sourceRef: row.source_ref,
    });
  }

  const ids = [...nodeDepth.keys()];
  const lexemeRows = (await sql`
		SELECT id, lang_code, headword, is_reconstructed
		FROM lexeme WHERE id = ANY(${ids})
	`) as Array<{
    id: string;
    lang_code: string;
    headword: string;
    is_reconstructed: boolean;
  }>;

  if (!lexemeRows.some((row) => row.id === focusId)) return null;

  return {
    focusId,
    nodes: lexemeRows.map((row) => ({
      id: row.id,
      langCode: row.lang_code,
      headword: row.headword,
      isReconstructed: row.is_reconstructed,
      depth: nodeDepth.get(row.id)!,
    })),
    edges: [...edgeByKey.values()],
  };
}
