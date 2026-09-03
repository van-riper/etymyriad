"""Post-merge fixups and index rebuild for the just-loaded rows."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg

_REBUILD_INDEXES_SQL = """
    SET maintenance_work_mem = '1GB';
    CREATE UNIQUE INDEX lexeme_natural_key
        ON lexeme (lang_code, headword, etym_key);
    CREATE INDEX lexeme_headword_trgm
        ON lexeme USING gin (headword ext.gin_trgm_ops);
    CREATE UNIQUE INDEX sense_natural_key
        ON sense (lexeme_id, pos_key, gloss_key);
    CREATE INDEX etymology_dst_idx ON etymology (dst_id);
    ALTER TABLE etymology
        ADD CONSTRAINT etymology_unique_edge
        UNIQUE (src_id, dst_id, rel_type);
"""

_REBUILD_DEGREE_INDEX_SQL = """
    CREATE INDEX lexeme_degree_idx ON lexeme (degree) WHERE degree > 0;
"""

_CLEAR_STALE_REDLINKS_SQL = """
    UPDATE lexeme SET is_redlink = false
    WHERE is_redlink
      AND EXISTS (
          SELECT 1 FROM lexeme AS real_entry
          WHERE real_entry.lang_code = lexeme.lang_code
            AND real_entry.headword = lexeme.headword
            AND NOT real_entry.is_redlink
      )
"""

# A template reference with no etymology_number can't say which of a
# split headword's sections it means, so it lands on an unnumbered stub
# that never collides with any of them.
# Once a real, numbered sibling exists, resolve the stub onto the
# lowest-numbered one (Wiktionary orders etymology sections for a
# reason, and the first is the best deterministic guess available
# without inventing a fact) by moving every edge that touches the stub
# onto that sibling, then deleting the stub. An edge is left on the
# stub, and the stub left undeleted, when moving it would create a
# self-loop -- a template can cite its own headword unnumbered
# specifically to point at a *different* section of itself (e.g.
# {{der|pt|pt|matreira|pos=etymology 1}} on "matreira" itself), and if
# that different section happens to be the lowest-numbered one, this is
# how that citation resolves back onto the same section that made it.
_MERGE_SPLIT_STUB_LEXEMES_SQL = """
    WITH target AS (
        SELECT DISTINCT ON (stub.id)
            stub.id AS stub_id, real_entry.id AS real_id
        FROM lexeme AS stub
        JOIN lexeme AS real_entry
          ON real_entry.lang_code = stub.lang_code
         AND real_entry.headword = stub.headword
         AND NOT real_entry.is_redlink
         AND real_entry.etym_key <> ''
        WHERE stub.is_redlink
          AND stub.etym_key = ''
        ORDER BY stub.id, real_entry.etymology_number ASC
    ),
    reassign_outgoing AS (
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                               piece_order)
        SELECT target.real_id, e.dst_id, e.rel_type, e.source_ref,
               e.piece_order
        FROM etymology AS e
        JOIN target ON target.stub_id = e.src_id
        WHERE target.real_id <> e.dst_id
          AND NOT EXISTS (
              SELECT 1 FROM etymology AS existing
              WHERE existing.src_id = target.real_id
                AND existing.dst_id = e.dst_id
                AND existing.rel_type = e.rel_type
          )
    ),
    reassign_incoming AS (
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                               piece_order)
        SELECT e.src_id, target.real_id, e.rel_type, e.source_ref,
               e.piece_order
        FROM etymology AS e
        JOIN target ON target.stub_id = e.dst_id
        WHERE target.real_id <> e.src_id
          AND NOT EXISTS (
              SELECT 1 FROM etymology AS existing
              WHERE existing.src_id = e.src_id
                AND existing.dst_id = target.real_id
                AND existing.rel_type = e.rel_type
          )
    ),
    safe_to_delete AS (
        SELECT target.stub_id
        FROM target
        WHERE NOT EXISTS (
            SELECT 1 FROM etymology AS e
            WHERE (e.src_id = target.stub_id AND e.dst_id = target.real_id)
               OR (e.dst_id = target.stub_id AND e.src_id = target.real_id)
        )
    )
    DELETE FROM lexeme WHERE id IN (SELECT stub_id FROM safe_to_delete)
"""

# A real dictionary entry (is_redlink already False, so the
# redlink-only stub fold above never touches it) can still land
# with no senses and an unnumbered etym_key, e.g. a page whose
# "Etymology" section has no numbered subsections of its own but whose
# headword also carries genuinely split, numbered siblings elsewhere in
# the dump. Fold it into its one numbered sibling the same way, when
# unambiguous; a stub matching more than one numbered sibling has no
# way to say which one it means, so it's left alone rather than
# guessed at.
_MERGE_SENSELESS_STUB_LEXEMES_SQL = """
    WITH candidate AS (
        SELECT stub.id AS stub_id,
               array_agg(real_entry.id) AS sibling_ids
        FROM lexeme AS stub
        JOIN lexeme AS real_entry
          ON real_entry.lang_code = stub.lang_code
         AND real_entry.headword = stub.headword
         AND real_entry.etym_key <> ''
        WHERE NOT stub.is_redlink
          AND stub.etym_key = ''
          AND NOT EXISTS (
              SELECT 1 FROM sense WHERE sense.lexeme_id = stub.id
          )
        GROUP BY stub.id
    ),
    target AS (
        SELECT stub_id, sibling_ids[1] AS real_id
        FROM candidate
        WHERE array_length(sibling_ids, 1) = 1
    ),
    reassign_outgoing AS (
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                               piece_order)
        SELECT target.real_id, e.dst_id, e.rel_type, e.source_ref,
               e.piece_order
        FROM etymology AS e
        JOIN target ON target.stub_id = e.src_id
        WHERE target.real_id <> e.dst_id
          AND NOT EXISTS (
              SELECT 1 FROM etymology AS existing
              WHERE existing.src_id = target.real_id
                AND existing.dst_id = e.dst_id
                AND existing.rel_type = e.rel_type
          )
    ),
    reassign_incoming AS (
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                               piece_order)
        SELECT e.src_id, target.real_id, e.rel_type, e.source_ref,
               e.piece_order
        FROM etymology AS e
        JOIN target ON target.stub_id = e.dst_id
        WHERE target.real_id <> e.src_id
          AND NOT EXISTS (
              SELECT 1 FROM etymology AS existing
              WHERE existing.src_id = e.src_id
                AND existing.dst_id = target.real_id
                AND existing.rel_type = e.rel_type
          )
    ),
    safe_to_delete AS (
        SELECT target.stub_id
        FROM target
        WHERE NOT EXISTS (
            SELECT 1 FROM etymology AS e
            WHERE (e.src_id = target.stub_id AND e.dst_id = target.real_id)
               OR (e.dst_id = target.stub_id AND e.src_id = target.real_id)
        )
    )
    DELETE FROM lexeme WHERE id IN (SELECT stub_id FROM safe_to_delete)
"""

# Recomputed after the merge and fixups, over every lexeme: the LEFT
# JOIN nets a fresh 0 for a lexeme with no edges, rather than leaving a
# stale nonzero degree in place.
_RECOMPUTE_DEGREE_SQL = """
    UPDATE lexeme SET degree = fresh_degree.degree
    FROM (
        SELECT l.id AS lexeme_id, COALESCE(degree_counts.degree, 0) AS degree
        FROM lexeme AS l
        LEFT JOIN (
            SELECT lexeme_id, sum(edge_count) AS degree
            FROM (
                SELECT src_id AS lexeme_id, count(*) AS edge_count
                FROM etymology GROUP BY src_id
                UNION ALL
                SELECT dst_id AS lexeme_id, count(*) AS edge_count
                FROM etymology GROUP BY dst_id
            ) AS endpoint_counts
            GROUP BY lexeme_id
        ) AS degree_counts ON degree_counts.lexeme_id = l.id
    ) AS fresh_degree
    WHERE lexeme.id = fresh_degree.lexeme_id
"""


def _fixup_and_index(cursor: psycopg.Cursor) -> None:
    """Fix up and index the just-merged rows.

    Indexes rebuild before the fixups run: the fixups' cascade deletes
    need etymology_dst_idx/etymology_unique_edge to avoid a full
    sequential scan of etymology per deleted row. lexeme_degree_idx is
    the one exception -- it's a partial index over degree > 0, so it
    must wait until after the degree recompute fills that column in.

    Args:
        cursor: Database cursor with an active connection; search_path
            must be set to `loading`.
    """
    _rebuild_indexes(cursor)
    _merge_split_stub_lexemes(cursor)
    _merge_senseless_stub_lexemes(cursor)
    _clear_stale_redlinks(cursor)
    _recompute_degree(cursor)
    _rebuild_degree_index(cursor)


def _rebuild_indexes(cursor: psycopg.Cursor) -> None:
    """Build the four bulk indexes plus etymology_unique_edge.

    Everything the earlier drop step removed except lexeme_degree_idx,
    which waits for a filled-in degree column. In bulk, with
    `maintenance_work_mem` bumped for this session only (measured at
    14.1s at 1GB, against a default of 64MB).
    """
    cursor.execute(_REBUILD_INDEXES_SQL)


def _rebuild_degree_index(cursor: psycopg.Cursor) -> None:
    """Build lexeme_degree_idx, once degree holds its final values."""
    cursor.execute(_REBUILD_DEGREE_INDEX_SQL)


def _recompute_degree(cursor: psycopg.Cursor) -> None:
    """Recompute every lexeme's degree from the etymology table."""
    cursor.execute(_RECOMPUTE_DEGREE_SQL)


def _merge_split_stub_lexemes(cursor: psycopg.Cursor) -> None:
    """Fold an unnumbered reference stub into its real, numbered sibling.

    Must run before the redlink-flag cleanup that follows: clearing the
    flag alone can't fix the split-headword gap, since it never
    reconnects the stub's edges to a real entry. Any stub this leaves
    behind (unsafe to delete, since folding it in would create a
    self-loop) still gets its flag cleared by that later step.
    """
    cursor.execute(_MERGE_SPLIT_STUB_LEXEMES_SQL)


def _merge_senseless_stub_lexemes(cursor: psycopg.Cursor) -> None:
    """Fold a senseless, unnumbered real entry into its one sibling.

    Unlike the redlink-only fold above, this targets entries that are
    already is_redlink=False -- a real dictionary page, not a template
    reference -- so it must run as a separate pass rather than
    widening that fold's own WHERE clause.
    """
    cursor.execute(_MERGE_SENSELESS_STUB_LEXEMES_SQL)


def _clear_stale_redlinks(cursor: psycopg.Cursor) -> None:
    """Clear a headword's redlink once a real entry exists for it.

    The merge's AND-latch only fires when a real entry shares the
    exact natural key, so a headword split by etymology_number
    (multiple numbered entries, no unnumbered one) never collides
    with its own unnumbered redlink stub.
    """
    cursor.execute(_CLEAR_STALE_REDLINKS_SQL)
