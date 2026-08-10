import { getSql } from './db';
import { MAX_SIBLINGS_PER_PARENT } from '$lib/tree/layout';
import type {
  EtymRelType,
  Language,
  Lexeme,
  LexemeSummary,
  Sense,
  TreeEdge,
  TreeNode,
  TreeOverflow,
  TreeSlice,
} from '$lib/shared/types';

type Sql = Awaited<ReturnType<typeof getSql>>;

// /tree has no UI-driven way to change this yet -- raise it if a
// deeper genealogy view turns out to be wanted.
const DEFAULT_TREE_DEPTH = 5;

type EdgeRow = {
  src_id: string;
  dst_id: string;
  rel_type: EtymRelType;
  source_ref: string;
  piece_order: number | null;
  depth: number;
};

type WalkRow = EdgeRow & { parent_id: string; total_children: number };

interface DirectionalWalk {
  rows: EdgeRow[];
  overflow: TreeOverflow[];
}

function summarizeWalk(
  rows: WalkRow[],
  cap: number,
  direction: 'ancestor' | 'descendant',
): DirectionalWalk {
  const overflowByParent = new Map<string, number>();
  for (const row of rows) {
    if (row.total_children > cap) {
      overflowByParent.set(row.parent_id, row.total_children - cap);
    }
  }
  return {
    rows,
    overflow: [...overflowByParent].map(([parentId, count]) => ({
      parentId,
      direction,
      count,
    })),
  };
}

// Walks descendants outward from anchorId, one hop per recursion step,
// keeping at most `cap` children per parent at every hop -- not just
// the final result set -- so a node with a massive fan-out (e.g. the
// English suffix "-ly", with 15k+ direct descendants) never inflates
// the query itself (ETYM-144). Each candidate child is first assigned
// to its single best-ranked parent edge (DISTINCT ON, mirroring
// treeLayout.ts's pickParentEdges), then ranked within that parent by
// the same relevance tiers pickParentEdges uses (direct lineage over
// morphology -- REL_TYPE_PRIORITY there, rel_priority here; keep both
// in sync). Ties break by the child's own id, not headword: headword
// lives in `lexeme`, a join this traversal skips on purpose to stay
// cheap. A same-tier tie can therefore survive the cap in a different
// order than the client's alphabetical tie-break would pick, but the
// relevance tier itself -- the property that actually bounds fan-out
// -- always agrees.
//
// startDepth/excludeIds let this same walk serve both the initial
// fetch (anchorId = focus, startDepth = 0, excludeIds = []) and a
// later "+N more" expansion (anchorId = an already-rendered parent,
// startDepth = its known depth, excludeIds = its already-fetched
// children).
async function walkDescendants(
  sql: Sql,
  anchorId: string,
  startDepth: number,
  maxDepth: number,
  cap: number,
  excludeIds: string[],
): Promise<DirectionalWalk> {
  const rows = (await sql`
    WITH RECURSIVE
    rel_priority(rel_type, priority) AS (
      VALUES
        ('inherited'::etym_rel_type, 0),
        ('borrowed'::etym_rel_type, 1),
        ('learned_borrowing'::etym_rel_type, 2),
        ('semi_learned_borrowing'::etym_rel_type, 3),
        ('derived'::etym_rel_type, 4),
        ('calque'::etym_rel_type, 5),
        ('compound'::etym_rel_type, 6),
        ('affix'::etym_rel_type, 7),
        ('surface_analysis'::etym_rel_type, 8),
        ('root'::etym_rel_type, 9),
        ('mention'::etym_rel_type, 10),
        ('cognate'::etym_rel_type, 11),
        ('onomatopoeic'::etym_rel_type, 12)
    ),
    walk AS (
      SELECT src_id, dst_id, rel_type, source_ref, piece_order, depth,
             src_id AS parent_id, total_children
      FROM (
        SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref, e.piece_order,
               ${startDepth} + 1 AS depth,
               row_number() OVER (ORDER BY rp.priority, e.dst_id) AS rn,
               count(*) OVER () AS total_children
        FROM etymology e
        JOIN rel_priority rp ON rp.rel_type = e.rel_type
        WHERE e.src_id = ${anchorId}
          AND e.dst_id != ALL(${excludeIds}::uuid[])
      ) ranked
      WHERE rn <= ${cap}
      UNION ALL
      SELECT src_id, dst_id, rel_type, source_ref, piece_order, depth,
             src_id AS parent_id, total_children
      FROM (
        SELECT owned.src_id, owned.dst_id, owned.rel_type, owned.source_ref,
               owned.piece_order, owned.depth,
               row_number() OVER (
                 PARTITION BY owned.src_id ORDER BY owned.priority, owned.dst_id
               ) AS rn,
               count(*) OVER (PARTITION BY owned.src_id) AS total_children
        FROM (
          SELECT DISTINCT ON (cand.dst_id)
            cand.src_id, cand.dst_id, cand.rel_type, cand.source_ref,
            cand.piece_order, cand.depth, cand.priority
          FROM (
            SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref,
                   e.piece_order, w.depth + 1 AS depth, rp.priority
            FROM etymology e
            JOIN rel_priority rp ON rp.rel_type = e.rel_type
            JOIN walk w ON e.src_id = w.dst_id
            WHERE w.depth < ${maxDepth}
          ) cand
          ORDER BY cand.dst_id, cand.priority, cand.src_id
        ) owned
      ) ranked
      WHERE rn <= ${cap}
    )
    SELECT src_id, dst_id, rel_type, source_ref, piece_order, depth,
           parent_id, total_children
    FROM walk
  `) as WalkRow[];

  return summarizeWalk(rows, cap, 'descendant');
}

// Mirror image of walkDescendants: walks ancestors outward from
// anchorId, capping fan-out per parent (here, the dst_id side) at
// every hop. See walkDescendants for the shared design rationale.
async function walkAncestors(
  sql: Sql,
  anchorId: string,
  startDepth: number,
  maxDepth: number,
  cap: number,
  excludeIds: string[],
): Promise<DirectionalWalk> {
  const rows = (await sql`
    WITH RECURSIVE
    rel_priority(rel_type, priority) AS (
      VALUES
        ('inherited'::etym_rel_type, 0),
        ('borrowed'::etym_rel_type, 1),
        ('learned_borrowing'::etym_rel_type, 2),
        ('semi_learned_borrowing'::etym_rel_type, 3),
        ('derived'::etym_rel_type, 4),
        ('calque'::etym_rel_type, 5),
        ('compound'::etym_rel_type, 6),
        ('affix'::etym_rel_type, 7),
        ('surface_analysis'::etym_rel_type, 8),
        ('root'::etym_rel_type, 9),
        ('mention'::etym_rel_type, 10),
        ('cognate'::etym_rel_type, 11),
        ('onomatopoeic'::etym_rel_type, 12)
    ),
    walk AS (
      SELECT src_id, dst_id, rel_type, source_ref, piece_order, depth,
             dst_id AS parent_id, total_children
      FROM (
        SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref, e.piece_order,
               ${startDepth} - 1 AS depth,
               row_number() OVER (ORDER BY rp.priority, e.src_id) AS rn,
               count(*) OVER () AS total_children
        FROM etymology e
        JOIN rel_priority rp ON rp.rel_type = e.rel_type
        WHERE e.dst_id = ${anchorId}
          AND e.src_id != ALL(${excludeIds}::uuid[])
      ) ranked
      WHERE rn <= ${cap}
      UNION ALL
      SELECT src_id, dst_id, rel_type, source_ref, piece_order, depth,
             dst_id AS parent_id, total_children
      FROM (
        SELECT owned.src_id, owned.dst_id, owned.rel_type, owned.source_ref,
               owned.piece_order, owned.depth,
               row_number() OVER (
                 PARTITION BY owned.dst_id ORDER BY owned.priority, owned.src_id
               ) AS rn,
               count(*) OVER (PARTITION BY owned.dst_id) AS total_children
        FROM (
          SELECT DISTINCT ON (cand.src_id)
            cand.src_id, cand.dst_id, cand.rel_type, cand.source_ref,
            cand.piece_order, cand.depth, cand.priority
          FROM (
            SELECT e.src_id, e.dst_id, e.rel_type, e.source_ref,
                   e.piece_order, w.depth - 1 AS depth, rp.priority
            FROM etymology e
            JOIN rel_priority rp ON rp.rel_type = e.rel_type
            JOIN walk w ON e.dst_id = w.src_id
            WHERE w.depth > ${-maxDepth}
          ) cand
          ORDER BY cand.src_id, cand.priority, cand.dst_id
        ) owned
      ) ranked
      WHERE rn <= ${cap}
    )
    SELECT src_id, dst_id, rel_type, source_ref, piece_order, depth,
           parent_id, total_children
    FROM walk
  `) as WalkRow[];

  return summarizeWalk(rows, cap, 'ancestor');
}

// Merges edge rows from one or more directional walks into a signed
// depth per node (seeded with the walk's own anchor), matching BFS: a
// DAG can reach the same node via more than one path at different
// depths, so the shortest survives. Shared by treeSlice (seeded at
// the focus, depth 0) and treeExpand (seeded at the expanded parent,
// its own already-known depth).
function mergeNodeDepths(
  seedId: string,
  seedDepth: number,
  edgeRows: EdgeRow[],
): Map<string, number> {
  const nodeDepth = new Map<string, number>([[seedId, seedDepth]]);
  for (const row of edgeRows) {
    const farId = row.depth < 0 ? row.src_id : row.dst_id;
    const known = nodeDepth.get(farId);
    if (known === undefined || Math.abs(row.depth) < Math.abs(known)) {
      nodeDepth.set(farId, row.depth);
    }
  }
  return nodeDepth;
}

function dedupeEdges(edgeRows: EdgeRow[]): TreeEdge[] {
  const edgeByKey = new Map<string, TreeEdge>();
  for (const row of edgeRows) {
    edgeByKey.set(`${row.src_id}:${row.dst_id}:${row.rel_type}`, {
      srcId: row.src_id,
      dstId: row.dst_id,
      relType: row.rel_type,
      sourceRef: row.source_ref,
      pieceOrder: row.piece_order,
    });
  }
  return [...edgeByKey.values()];
}

async function fetchNodes(
  sql: Sql,
  ids: string[],
  depthOf: Map<string, number>,
): Promise<TreeNode[]> {
  if (ids.length === 0) return [];
  const lexemeRows = (await sql`
		SELECT id, lang_code, headword, is_reconstructed
		FROM lexeme WHERE id = ANY(${ids})
	`) as Array<{
    id: string;
    lang_code: string;
    headword: string;
    is_reconstructed: boolean;
  }>;

  return lexemeRows.map((row) => ({
    id: row.id,
    langCode: row.lang_code,
    headword: row.headword,
    isReconstructed: row.is_reconstructed,
    depth: depthOf.get(row.id)!,
  }));
}

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
// no notion of (x, y). Fan-out per parent is capped during the walk
// itself (see walkAncestors/walkDescendants) rather than after
// fetching everything, so a focus word with a massive fan-out (e.g.
// English "-ly", 15k+ direct descendants) stays a bounded query
// instead of a multi-second one (ETYM-144).
export async function treeSlice(
  focusId: string,
  maxDepth: number = DEFAULT_TREE_DEPTH,
): Promise<TreeSlice | null> {
  const sql = await getSql();

  const ancestorWalk = await walkAncestors(
    sql,
    focusId,
    0,
    maxDepth,
    MAX_SIBLINGS_PER_PARENT,
    [],
  );
  const descendantWalk = await walkDescendants(
    sql,
    focusId,
    0,
    maxDepth,
    MAX_SIBLINGS_PER_PARENT,
    [],
  );
  const edgeRows = [...ancestorWalk.rows, ...descendantWalk.rows];
  const overflow = [...ancestorWalk.overflow, ...descendantWalk.overflow];

  const nodeDepth = mergeNodeDepths(focusId, 0, edgeRows);
  const nodes = await fetchNodes(sql, [...nodeDepth.keys()], nodeDepth);

  if (!nodes.some((node) => node.id === focusId)) return null;

  return { focusId, nodes, edges: dedupeEdges(edgeRows), overflow };
}

// Fetches the next batch (up to MAX_SIBLINGS_PER_PARENT) of parentId's
// children beyond what the caller already has, in one direction, plus
// their own capped descendants down to maxDepth -- the "+N more"
// affordance's fetch, scoped to exactly what it reveals rather than a
// re-slice of an already-fetched oversized payload (ETYM-144).
// parentDepth is parentId's own already-known signed depth, so the
// walk continues from the right point in the overall maxDepth budget.
export async function treeExpand(
  parentId: string,
  direction: 'ancestor' | 'descendant',
  parentDepth: number,
  excludeIds: string[],
  maxDepth: number = DEFAULT_TREE_DEPTH,
): Promise<{ nodes: TreeNode[]; edges: TreeEdge[]; overflow: TreeOverflow[] }> {
  const sql = await getSql();

  const walk =
    direction === 'ancestor'
      ? await walkAncestors(
          sql,
          parentId,
          parentDepth,
          maxDepth,
          MAX_SIBLINGS_PER_PARENT,
          excludeIds,
        )
      : await walkDescendants(
          sql,
          parentId,
          parentDepth,
          maxDepth,
          MAX_SIBLINGS_PER_PARENT,
          excludeIds,
        );

  const nodeDepth = mergeNodeDepths(parentId, parentDepth, walk.rows);
  nodeDepth.delete(parentId); // already known to the caller
  const nodes = await fetchNodes(sql, [...nodeDepth.keys()], nodeDepth);

  return { nodes, edges: dedupeEdges(walk.rows), overflow: walk.overflow };
}
