"""Index, derive, vacuum, and gate a merged `loading` generation."""

from typing import TYPE_CHECKING

import psycopg
import psycopg.sql

from etymyriad.config import (
    INDEX_BUILD_MAINTENANCE_WORK_MEM,
    MAX_UNKNOWN_LANGUAGE_SHARE,
)
from etymyriad.load._timing import logged_step

if TYPE_CHECKING:
    from etymyriad.load._merge import MergeCounts

_BUILD_INDEXES_SQL = f"""
    SET maintenance_work_mem = '{INDEX_BUILD_MAINTENANCE_WORK_MEM}';
    ALTER TABLE term
        ADD CONSTRAINT term_natural_key UNIQUE (language_id, headword);
    CREATE INDEX sense_term_idx ON sense (term_id);
    ALTER TABLE edge ADD CONSTRAINT edge_pkey PRIMARY KEY
        (src_term_id, dst_term_id, dst_section, rel_type, src_section);
    CREATE INDEX edge_dst_idx ON edge (dst_term_id, dst_section);
"""

_FILL_PICKABLE_TERMS_SQL = """
    INSERT INTO pickable_term (term_id, language_id)
    SELECT term.id, term.language_id
    FROM term
    WHERE EXISTS (SELECT 1 FROM sense WHERE sense.term_id = term.id)
      AND term.id IN (
          SELECT src_term_id FROM edge WHERE rel_type <> 'mention'
          UNION
          SELECT dst_term_id FROM edge WHERE rel_type <> 'mention'
      );
    CREATE INDEX pickable_term_language_idx
        ON pickable_term (language_id, term_id);
"""


def _build_indexes(cursor: psycopg.Cursor) -> None:
    """Build the keys and indexes the bulk merge deferred."""
    with logged_step("build indexes"):
        cursor.execute(_BUILD_INDEXES_SQL)


def _fill_pickable_terms(cursor: psycopg.Cursor) -> None:
    """Fill `pickable_term` with real, connected terms and index it."""
    with logged_step("fill pickable terms"):
        cursor.execute(_FILL_PICKABLE_TERMS_SQL)


def _check_unknown_languages_or_raise(counts: MergeCounts) -> None:
    """Refuse a load that dropped too many edges to unknown codes.

    A handful (one today) is a Wiktionary typo; more means the registry
    snapshot is stale, and the reload should sync it first.

    Args:
        counts: The merge's staged and dropped edge counts.

    Raises:
        RuntimeError: If unknown codes cost more than 0.1% of edges.
    """
    if not counts.staged_edges:
        return
    share = counts.unknown_language_edges / counts.staged_edges
    if share > MAX_UNKNOWN_LANGUAGE_SHARE:
        msg = (
            f"{counts.unknown_language_edges:,} of {counts.staged_edges:,} "
            "staged edges name an unknown language code; run "
            "`etymyriad sync-languages` and reload"
        )
        raise RuntimeError(msg)


def _vacuum_analyze(connection: psycopg.Connection) -> None:
    """Set hint bits and planner stats before the site reads the tables.

    VACUUM can't run inside a transaction, so each table is its own
    autocommit statement.
    """
    for table in ("term", "sense", "edge", "pickable_term"):
        with logged_step(f"vacuum {table}"):
            connection.execute(
                psycopg.sql.SQL("VACUUM (ANALYZE) loading.{}").format(
                    psycopg.sql.Identifier(table)
                )
            )
