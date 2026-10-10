import { getSql } from './db';
import { MAX_SIBLINGS_PER_PARENT } from '$lib/tree/layout';
import type {
  EtymRelType,
  Language,
  Term,
  TermSummary,
  TreeEdge,
  TreeNode,
  TreeOverflow,
  TreeSlice,
} from '$lib/shared/types';

type Sql = Awaited<ReturnType<typeof getSql>>;

// Neither direction is caller-bounded: a survey of 2,000 random
// non-leaf terms found the deepest legitimate descendant chain at
// 11 hops and 98.9% terminating naturally by hop 5, so a fixed depth
// cap was cutting off real genealogy for almost no benefit. But the
// edge table has no DB-level cycle constraint, and at least one
// real cycle exists (sa "कागद" <-> hi/mr/kok/mwr "कागद", each citing
// the other as source), confirmed by this same survey, which found
// it still growing at 50 hops. Without any ceiling, walking that
// node's descendants (or its mirror image in walkAncestors) would
// recurse forever. This is a loop breaker, not a UI limit: no
// legitimate chain has ever come close to it.
// ponytail: hop-count ceiling, not real cycle detection. Add a
// CYCLE clause (Postgres 14+) if a cycle ever needs breaking earlier
// than 100 hops in.
const WALK_SAFETY_LIMIT = 100;

type EdgeRow = {
  src_id: number;
  dst_id: number;
  rel_type: EtymRelType;
  source_ref: string;
  piece_order: number | null;
  depth: number;
};

type WalkRow = EdgeRow & { parent_id: number; total_children: number };

interface DirectionalWalk {
  rows: EdgeRow[];
  overflow: TreeOverflow[];
}

function summarizeWalk(
  rows: WalkRow[],
  cap: number,
  direction: 'ancestor' | 'descendant',
): DirectionalWalk {
  const overflowByParent = new Map<number, number>();
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
// keeping at most `cap` children per parent at every hop (not just
// the final result set), so a node with a massive fan-out (e.g. the
// English suffix "-ly", with 15k+ direct descendants) never inflates
// the query itself. Each candidate child is first assigned to its
// single best-ranked parent edge (DISTINCT ON, mirroring
// tree/layout/parentEdges.ts's pickParentEdges), then ranked within
// that parent by
// the same relevance tiers pickParentEdges uses (direct lineage over
// morphology; REL_TYPE_PRIORITY there, rel_priority here; keep both
// in sync). Ties break by the child's own id, not headword: headword
// lives in `term`, a join this traversal skips on purpose to stay
// cheap. A same-tier tie can therefore survive the cap in a different
// order than the client's alphabetical tie-break would pick, but the
// relevance tier itself (the property that actually bounds fan-out)
// always agrees.
//
// startDepth/excludeIds let this same walk serve both the initial
// fetch (anchorId = focus, startDepth = 0, excludeIds = []) and a
// later "+N more" expansion (anchorId = an already-rendered parent,
// startDepth = its known depth, excludeIds = its already-fetched
// children). Depth is not caller-bounded: see WALK_SAFETY_LIMIT.
//
// A section of 0 on either side of a hop means "unspecified" and
// matches any section; the citation is composed over the bounded
// result only.
async function walkDescendants(
  sql: Sql,
  anchorId: number,
  anchorSection: number,
  startDepth: number,
  cap: number,
  excludeIds: number[],
): Promise<DirectionalWalk> {
  const rows = (await sql`
    WITH RECURSIVE
    rel_priority(rel_type, priority) AS (
      VALUES
        ('inherited'::edge_type, 0),
        ('borrowed'::edge_type, 1),
        ('learned_borrowing'::edge_type, 2),
        ('semi_learned_borrowing'::edge_type, 3),
        ('derived'::edge_type, 4),
        ('inflection'::edge_type, 5),
        ('calque'::edge_type, 6),
        ('compound'::edge_type, 7),
        ('affix'::edge_type, 8),
        ('surface_analysis'::edge_type, 9),
        ('root'::edge_type, 10)
    ),
    walk AS (
      SELECT src_id, dst_id, src_section, dst_section, rel_type, anchor,
             piece_order, depth, src_id AS parent_id, total_children
      FROM (
        SELECT src_id, dst_id, src_section, dst_section, rel_type, anchor,
               piece_order, depth, dr, max(dr) OVER () AS total_children
        FROM (
          SELECT src_id, dst_id, src_section, dst_section, rel_type, anchor,
                 piece_order, depth,
                 dense_rank() OVER (ORDER BY best, dst_id) AS dr
          FROM (
            SELECT e.src_term_id AS src_id, e.dst_term_id AS dst_id,
                   e.src_section, e.dst_section, e.rel_type, e.anchor,
                   e.piece_order, ${startDepth} + 1 AS depth,
                   min(rp.priority) OVER (PARTITION BY e.dst_term_id) AS best
            FROM edge e
            JOIN rel_priority rp ON rp.rel_type = e.rel_type
            WHERE e.src_term_id = ${anchorId}
              AND (e.src_section = 0 OR ${anchorSection}::int = 0
                   OR e.src_section = ${anchorSection})
              AND e.dst_term_id != ALL(${excludeIds}::int[])
          ) prioritized
        ) ranked_children
      ) ranked
      WHERE dr <= ${cap}
      UNION ALL
      SELECT src_id, dst_id, src_section, dst_section, rel_type, anchor,
             piece_order, depth, src_id AS parent_id, total_children
      FROM (
        SELECT owned.src_id, owned.dst_id, owned.src_section,
               owned.dst_section, owned.rel_type, owned.anchor,
               owned.piece_order, owned.depth,
               row_number() OVER (
                 PARTITION BY owned.src_id ORDER BY owned.priority, owned.dst_id
               ) AS rn,
               count(*) OVER (PARTITION BY owned.src_id) AS total_children
        FROM (
          SELECT DISTINCT ON (cand.dst_id)
            cand.src_id, cand.dst_id, cand.src_section, cand.dst_section,
            cand.rel_type, cand.anchor, cand.piece_order, cand.depth,
            cand.priority
          FROM (
            SELECT e.src_term_id AS src_id, e.dst_term_id AS dst_id,
                   e.src_section, e.dst_section, e.rel_type, e.anchor,
                   e.piece_order, w.depth + 1 AS depth, rp.priority
            FROM edge e
            JOIN rel_priority rp ON rp.rel_type = e.rel_type
            JOIN walk w ON e.src_term_id = w.dst_id
                       AND (e.src_section = 0 OR w.dst_section = 0
                            OR e.src_section = w.dst_section)
            WHERE w.depth < ${WALK_SAFETY_LIMIT}
          ) cand
          ORDER BY cand.dst_id, cand.priority, cand.src_id
        ) owned
      ) ranked
      WHERE rn <= ${cap}
    )
    SELECT w.src_id, w.dst_id, w.rel_type,
           (SELECT source_ref(dl.code, d.headword, w.anchor, w.dst_section)
            FROM term d JOIN language dl ON dl.id = d.language_id
            WHERE d.id = w.dst_id) AS source_ref,
           w.piece_order, w.depth, w.parent_id, w.total_children
    FROM walk w
  `) as WalkRow[];

  return summarizeWalk(rows, cap, 'descendant');
}

// Mirror image of walkDescendants: walks ancestors outward from
// anchorId, capping fan-out per parent (here, the dst_id side) at
// every hop. See walkDescendants for the shared design rationale,
// including depth not being caller-bounded (WALK_SAFETY_LIMIT).
async function walkAncestors(
  sql: Sql,
  anchorId: number,
  anchorSection: number,
  startDepth: number,
  cap: number,
  excludeIds: number[],
): Promise<DirectionalWalk> {
  const rows = (await sql`
    WITH RECURSIVE
    rel_priority(rel_type, priority) AS (
      VALUES
        ('inherited'::edge_type, 0),
        ('borrowed'::edge_type, 1),
        ('learned_borrowing'::edge_type, 2),
        ('semi_learned_borrowing'::edge_type, 3),
        ('derived'::edge_type, 4),
        ('inflection'::edge_type, 5),
        ('calque'::edge_type, 6),
        ('compound'::edge_type, 7),
        ('affix'::edge_type, 8),
        ('surface_analysis'::edge_type, 9),
        ('root'::edge_type, 10)
    ),
    walk AS (
      SELECT src_id, dst_id, src_section, dst_section, rel_type, anchor,
             piece_order, depth, dst_id AS parent_id, total_children
      FROM (
        SELECT src_id, dst_id, src_section, dst_section, rel_type, anchor,
               piece_order, depth, dr, max(dr) OVER () AS total_children
        FROM (
          SELECT src_id, dst_id, src_section, dst_section, rel_type, anchor,
                 piece_order, depth,
                 dense_rank() OVER (ORDER BY best, src_id) AS dr
          FROM (
            SELECT e.src_term_id AS src_id, e.dst_term_id AS dst_id,
                   e.src_section, e.dst_section, e.rel_type, e.anchor,
                   e.piece_order, ${startDepth} - 1 AS depth,
                   min(rp.priority) OVER (PARTITION BY e.src_term_id) AS best
            FROM edge e
            JOIN rel_priority rp ON rp.rel_type = e.rel_type
            WHERE e.dst_term_id = ${anchorId}
              AND (${anchorSection}::int = 0
                   OR e.dst_section = ${anchorSection})
              AND e.src_term_id != ALL(${excludeIds}::int[])
          ) prioritized
        ) ranked_children
      ) ranked
      WHERE dr <= ${cap}
      UNION ALL
      SELECT src_id, dst_id, src_section, dst_section, rel_type, anchor,
             piece_order, depth, dst_id AS parent_id, total_children
      FROM (
        SELECT owned.src_id, owned.dst_id, owned.src_section,
               owned.dst_section, owned.rel_type, owned.anchor,
               owned.piece_order, owned.depth,
               row_number() OVER (
                 PARTITION BY owned.dst_id ORDER BY owned.priority, owned.src_id
               ) AS rn,
               count(*) OVER (PARTITION BY owned.dst_id) AS total_children
        FROM (
          SELECT DISTINCT ON (cand.src_id)
            cand.src_id, cand.dst_id, cand.src_section, cand.dst_section,
            cand.rel_type, cand.anchor, cand.piece_order, cand.depth,
            cand.priority
          FROM (
            SELECT e.src_term_id AS src_id, e.dst_term_id AS dst_id,
                   e.src_section, e.dst_section, e.rel_type, e.anchor,
                   e.piece_order, w.depth - 1 AS depth, rp.priority
            FROM edge e
            JOIN rel_priority rp ON rp.rel_type = e.rel_type
            JOIN walk w ON e.dst_term_id = w.src_id
                       AND (w.src_section = 0 OR e.dst_section = w.src_section)
            WHERE w.depth > ${-WALK_SAFETY_LIMIT}
          ) cand
          ORDER BY cand.src_id, cand.priority, cand.dst_id
        ) owned
      ) ranked
      WHERE rn <= ${cap}
    )
    SELECT w.src_id, w.dst_id, w.rel_type,
           (SELECT source_ref(dl.code, d.headword, w.anchor, w.dst_section)
            FROM term d JOIN language dl ON dl.id = d.language_id
            WHERE d.id = w.dst_id) AS source_ref,
           w.piece_order, w.depth, w.parent_id, w.total_children
    FROM walk w
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
  seedId: number,
  seedDepth: number,
  edgeRows: EdgeRow[],
): Map<number, number> {
  const nodeDepth = new Map<number, number>([[seedId, seedDepth]]);
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
  ids: number[],
  depthOf: Map<number, number>,
): Promise<TreeNode[]> {
  if (ids.length === 0) return [];
  const termRows = (await sql`
    SELECT t.id, l.code AS lang_code, t.headword, t.is_reconstructed,
           NOT EXISTS (SELECT 1 FROM sense s WHERE s.term_id = t.id)
             AS is_redlink
    FROM term t JOIN language l ON l.id = t.language_id
    WHERE t.id = ANY(${ids}::int[])
  `) as Array<{
    id: number;
    lang_code: string;
    headword: string;
    is_reconstructed: boolean;
    is_redlink: boolean;
  }>;

  return termRows.map((row) => ({
    id: row.id,
    langCode: row.lang_code,
    headword: row.headword,
    isReconstructed: row.is_reconstructed,
    isRedlink: row.is_redlink,
    depth: depthOf.get(row.id)!,
  }));
}

// Probes pickable_term's id range at a random point instead of
// ORDER BY random(), which full-scans. The language filter is
// repeated rather than shared in a CTE, which Postgres materializes
// and scans whole. Restricted to langCode when given, otherwise any
// language.
// shortcut: pickable_term ids have gaps (about 1.6M of 8.3M term ids),
// so a term after a gap is likelier to win; precompute a uniform
// sampler if that skew ever matters.
export async function randomTerm(langCode?: string): Promise<{
  langCode: string;
  headword: string;
} | null> {
  const sql = await getSql();
  const lang = langCode ?? null;
  const rows = (await sql`
    WITH bounds AS (
      SELECT min(term_id) AS lo, max(term_id) AS hi FROM pickable_term
      WHERE ${lang}::text IS NULL
         OR language_id = (SELECT id FROM language WHERE code = ${lang})
    )
    SELECT l.code AS lang_code, t.headword
    FROM bounds,
    LATERAL (
      SELECT term_id, language_id FROM pickable_term
      WHERE (${lang}::text IS NULL
             OR language_id = (SELECT id FROM language WHERE code = ${lang}))
        AND term_id >= bounds.lo
        + floor(${Math.random()}::float8 * (bounds.hi - bounds.lo + 1))::int
      ORDER BY term_id LIMIT 1
    ) AS pick
    JOIN term t ON t.id = pick.term_id
    JOIN language l ON l.id = pick.language_id
  `) as Array<{ lang_code: string; headword: string }>;
  return rows.length
    ? { langCode: rows[0].lang_code, headword: rows[0].headword }
    : null;
}

// Fetches every pickable language's code/name, for the client-side
// language typeahead. Small enough to ship whole and rank in the
// browser rather than round-tripping per keystroke. A language with
// no pickable term would 404 on randomTerm, so it doesn't belong in a
// search box meant to lead somewhere.
export async function languageList(): Promise<Language[]> {
  const sql = await getSql();

  return (await sql`
    SELECT l.code, l.name FROM language l
    WHERE EXISTS (SELECT 1 FROM pickable_term p WHERE p.language_id = l.id)
    ORDER BY l.code
  `) as Array<{ code: string; name: string }>;
}

// Fetches one term's attribute-tier detail (senses, source_ref,
// etc.) by id: the lazy per-node fetch triggered by clicking a node.
export async function termDetail(id: number): Promise<Term | null> {
  const sql = await getSql();

  const rows = (await sql`
    SELECT t.id, l.code AS lang_code, l.name AS lang_name, t.headword,
           t.is_reconstructed, source_ref(l.code, t.headword) AS source_ref
    FROM term t JOIN language l ON l.id = t.language_id
    WHERE t.id = ${id}
  `) as Array<{
    id: number;
    lang_code: string;
    lang_name: string;
    headword: string;
    is_reconstructed: boolean;
    source_ref: string;
  }>;

  if (rows.length === 0) return null;
  const row = rows[0];

  const senseRows = (await sql`
    SELECT section, part_of_speech, gloss FROM sense
    WHERE term_id = ${id}
    ORDER BY section, part_of_speech NULLS FIRST, gloss NULLS FIRST
  `) as Array<{
    section: number;
    part_of_speech: string | null;
    gloss: string | null;
  }>;

  return {
    id: row.id,
    langCode: row.lang_code,
    langName: row.lang_name,
    headword: row.headword,
    isReconstructed: row.is_reconstructed,
    isRedlink: senseRows.length === 0,
    sourceRef: row.source_ref,
    senses: senseRows.map((s) => ({
      section: s.section,
      partOfSpeech: s.part_of_speech,
      gloss: s.gloss,
    })),
  };
}

// Resolves a (lang, headword) pair to one summary per section, for
// /tree's focus word lookup: a homograph term has several sections
// (Wiktionary's "Etymology N"), each its own family tree. Pass
// section to narrow to one; it may match nothing. A redlink has no
// sense rows and yields a single section-0 summary.
export async function termsByHeadword(
  lang: string,
  headword: string,
  section?: number,
): Promise<TermSummary[]> {
  const sql = await getSql();

  const termRows = (await sql`
    SELECT t.id FROM term t JOIN language l ON l.id = t.language_id
    WHERE l.code = ${lang} AND t.headword = ${headword}
  `) as Array<{ id: number }>;
  if (termRows.length === 0) return [];
  const { id } = termRows[0];

  const senseRows = (await sql`
    SELECT DISTINCT ON (section) section, part_of_speech, gloss FROM sense
    WHERE term_id = ${id}
    ORDER BY section, part_of_speech NULLS FIRST, gloss NULLS LAST
  `) as Array<{
    section: number;
    part_of_speech: string | null;
    gloss: string | null;
  }>;

  const summaries: TermSummary[] = senseRows.length
    ? senseRows.map((s) => ({
        id,
        section: s.section,
        partOfSpeech: s.part_of_speech,
        gloss: s.gloss,
      }))
    : [{ id, section: 0, partOfSpeech: null, gloss: null }];

  return section === undefined
    ? summaries
    : summaries.filter((s) => s.section === section);
}

// Bounded bidirectional BFS from a focus term: every ancestor and
// descendant the data has (see WALK_SAFETY_LIMIT for the one
// loop-breaking exception), each tagged with its signed BFS
// generation distance from the focus (negative = ancestor, positive =
// descendant, 0 = the focus itself). Powers /tree's genealogy view,
// which has no notion of (x, y). Fan-out per parent is capped during
// the walk itself (see walkAncestors/walkDescendants) rather than
// after fetching everything, so a focus word with a massive fan-out
// (e.g. English "-ly", 15k+ direct descendants) stays a bounded query
// instead of a multi-second one. section narrows the focus's first
// hop to one "Etymology N" (0 = every section).
export async function treeSlice(
  focusId: number,
  section: number,
): Promise<TreeSlice | null> {
  const sql = await getSql();

  const ancestorWalk = await walkAncestors(
    sql,
    focusId,
    section,
    0,
    MAX_SIBLINGS_PER_PARENT,
    [],
  );
  const descendantWalk = await walkDescendants(
    sql,
    focusId,
    section,
    0,
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
// children beyond what the caller already has, in one direction:
// the "+N more" affordance's fetch, scoped to exactly what it reveals
// rather than a re-slice of an already-fetched oversized payload.
// Neither direction is depth-bounded, same as treeSlice.
// parentDepth is parentId's own already-known signed depth, so the
// walk continues from the right point relative to the focus. The
// first hop takes every section: an expansion parent is never the
// focus's own section.
export async function treeExpand(
  parentId: number,
  direction: 'ancestor' | 'descendant',
  parentDepth: number,
  excludeIds: number[],
): Promise<{ nodes: TreeNode[]; edges: TreeEdge[]; overflow: TreeOverflow[] }> {
  const sql = await getSql();

  const walk =
    direction === 'ancestor'
      ? await walkAncestors(
          sql,
          parentId,
          0,
          parentDepth,
          MAX_SIBLINGS_PER_PARENT,
          excludeIds,
        )
      : await walkDescendants(
          sql,
          parentId,
          0,
          parentDepth,
          MAX_SIBLINGS_PER_PARENT,
          excludeIds,
        );

  const nodeDepth = mergeNodeDepths(parentId, parentDepth, walk.rows);
  nodeDepth.delete(parentId); // already known to the caller
  const nodes = await fetchNodes(sql, [...nodeDepth.keys()], nodeDepth);

  return { nodes, edges: dedupeEdges(walk.rows), overflow: walk.overflow };
}
