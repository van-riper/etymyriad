"""Upsert the etymology graph into Postgres.

Idempotent: re-running with the same data produces the same rows. Lexemes are
upserted on their natural key, edges on (src, dst, rel_type). Each chunk is
sent as one batch (psycopg pipelines the statements) and committed on its
own, so a large load neither holds one giant transaction nor pays a network
round trip per row.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg
import psycopg.sql

from etymyriad.languages import language_family, language_name
from etymyriad.model import PROTO_LANG_SUFFIX, EtymEdge

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from uuid import UUID

    from etymyriad.model import Lexeme

_log = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 1000
_PROGRESS_INTERVAL_SECONDS = 10

_TARGET_SCHEMA = "loading"

_LEXEME_STAGE_COLUMNS = (
    "lang_code",
    "headword",
    "etymology_number",
    "romanization",
    "is_reconstructed",
    "is_redlink",
    "source_ref",
    "pos",
    "gloss",
    "has_sense",
)
_EDGE_STAGE_COLUMNS = (
    "src_lang_code",
    "src_headword",
    "src_etymology_number",
    "dst_lang_code",
    "dst_headword",
    "dst_etymology_number",
    "rel_type",
    "source_ref",
    "piece_order",
)

_STAGING_DDL_SQL = """
    CREATE UNLOGGED TABLE stg_lexeme (
        lang_code TEXT NOT NULL,
        headword TEXT NOT NULL,
        etymology_number TEXT,
        romanization TEXT,
        is_reconstructed BOOLEAN NOT NULL,
        is_redlink BOOLEAN NOT NULL,
        source_ref TEXT NOT NULL,
        pos TEXT,
        gloss TEXT,
        has_sense BOOLEAN NOT NULL
    );

    CREATE UNLOGGED TABLE stg_edge (
        src_lang_code TEXT NOT NULL,
        src_headword TEXT NOT NULL,
        src_etymology_number TEXT,
        dst_lang_code TEXT NOT NULL,
        dst_headword TEXT NOT NULL,
        dst_etymology_number TEXT,
        rel_type TEXT NOT NULL,
        source_ref TEXT NOT NULL,
        piece_order SMALLINT
    );
"""

_SCHEMA_SQL_PATH = str(
    Path(__file__).resolve().parents[3] / "db" / "schema.sql"
)

_DROP_DEFERRED_INDEXES_SQL = """
    DROP INDEX lexeme_natural_key;
    DROP INDEX lexeme_headword_trgm;
    DROP INDEX lexeme_degree_idx;
    DROP INDEX sense_natural_key;
    DROP INDEX etymology_dst_idx;
    ALTER TABLE etymology DROP CONSTRAINT etymology_unique_edge;
"""

_REBUILD_INDEXES_SQL = """
    SET maintenance_work_mem = '1GB';
    CREATE UNIQUE INDEX lexeme_natural_key
        ON lexeme (lang_code, headword, etym_key);
    CREATE INDEX lexeme_headword_trgm
        ON lexeme USING gin (headword ext.gin_trgm_ops);
    CREATE INDEX lexeme_degree_idx
        ON lexeme (degree) WHERE degree > 0;
    CREATE UNIQUE INDEX sense_natural_key
        ON sense (lexeme_id, pos_key, gloss_key);
    CREATE INDEX etymology_dst_idx ON etymology (dst_id);
    ALTER TABLE etymology
        ADD CONSTRAINT etymology_unique_edge
        UNIQUE (src_id, dst_id, rel_type);
"""

_LANGUAGE_UPSERT_SQL = """
    INSERT INTO language (code, name, lang_family, is_proto)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (code) DO UPDATE SET
        name = EXCLUDED.name,
        lang_family = EXCLUDED.lang_family,
        is_proto = EXCLUDED.is_proto
"""

_LEXEME_UPSERT_SQL = """
    INSERT INTO lexeme (lang_code, headword, etymology_number, romanization,
                        is_reconstructed, is_redlink, source_ref, loaded_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (lang_code, headword, etym_key)
    DO UPDATE SET
        romanization = COALESCE(EXCLUDED.romanization,
                                lexeme.romanization),
        is_reconstructed = lexeme.is_reconstructed
                           OR EXCLUDED.is_reconstructed,
        is_redlink = lexeme.is_redlink AND EXCLUDED.is_redlink,
        source_ref = EXCLUDED.source_ref,
        loaded_at = EXCLUDED.loaded_at
    RETURNING id
"""

_SENSE_UPSERT_SQL = """
    INSERT INTO sense (lexeme_id, pos, gloss, source_ref, loaded_at)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (lexeme_id, pos_key, gloss_key)
    DO UPDATE SET
        source_ref = EXCLUDED.source_ref,
        loaded_at = EXCLUDED.loaded_at
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

_EDGE_UPSERT_SQL = """
    INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                           piece_order, loaded_at)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (src_id, dst_id, rel_type) DO UPDATE SET
        piece_order = EXCLUDED.piece_order,
        loaded_at = EXCLUDED.loaded_at
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

_MERGE_LEXEMES_SQL = """
    INSERT INTO lexeme (lang_code, headword, etymology_number,
                        romanization, is_reconstructed, is_redlink,
                        source_ref)
    SELECT lang_code, headword, etymology_number,
           max(romanization), bool_or(is_reconstructed),
           bool_and(is_redlink), max(source_ref)
    FROM stg_lexeme
    GROUP BY lang_code, headword, etymology_number
"""

_MERGE_SENSES_SQL = """
    INSERT INTO sense (lexeme_id, pos, gloss, source_ref)
    SELECT DISTINCT l.id, s.pos, s.gloss, s.source_ref
    FROM stg_lexeme AS s
    JOIN lexeme AS l
      ON l.lang_code = s.lang_code
     AND l.headword = s.headword
     AND l.etym_key = COALESCE(s.etymology_number, '')
    WHERE s.has_sense
"""

_MERGE_EDGES_SQL = """
    INSERT INTO etymology (src_id, dst_id, rel_type, source_ref,
                           piece_order)
    SELECT src.id, dst.id, e.rel_type::etym_rel_type, max(e.source_ref),
           max(e.piece_order)
    FROM stg_edge AS e
    JOIN lexeme AS src
      ON src.lang_code = e.src_lang_code
     AND src.headword = e.src_headword
     AND src.etym_key = COALESCE(e.src_etymology_number, '')
    JOIN lexeme AS dst
      ON dst.lang_code = e.dst_lang_code
     AND dst.headword = e.dst_headword
     AND dst.etym_key = COALESCE(e.dst_etymology_number, '')
    GROUP BY src.id, dst.id, e.rel_type
"""

_DROP_STAGING_SQL = "DROP TABLE stg_lexeme, stg_edge"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _merge_staged_data(
    cursor: psycopg.Cursor, seen_languages: Iterable[str]
) -> None:
    """Resolve staged natural keys into lexeme/sense/etymology rows.

    Aggregates every staged occurrence of a natural key in one pass:
    `is_reconstructed` OR-latches, `is_redlink` AND-latches, and
    `romanization`/`source_ref` take any non-null value (both are
    deterministic per natural key within one run's dump, so any
    occurrence's value is as good as any other's). Drops the staging
    tables once resolved, so they never survive into `public`.

    Args:
        cursor: Database cursor with an active connection; search_path
            must be set to `loading`.
        seen_languages: Language codes encountered during staging.
    """
    cursor.executemany(
        _LANGUAGE_UPSERT_SQL,
        [
            (
                code,
                language_name(code) or code,
                language_family(code),
                code.endswith(PROTO_LANG_SUFFIX),
            )
            for code in seen_languages
        ],
    )
    cursor.execute(_MERGE_LEXEMES_SQL)
    cursor.execute(_MERGE_SENSES_SQL)
    cursor.execute(_MERGE_EDGES_SQL)
    cursor.execute(_DROP_STAGING_SQL)


def _lexeme_stage_row(lexeme: Lexeme) -> tuple[object, ...]:
    """Flatten a lexeme occurrence, plus its at-most-one sense.

    Returns:
        A tuple of (lang_code, headword, etymology_number, romanization,
            is_reconstructed, is_redlink, source_ref, pos, gloss,
            has_sense).

    Raises:
        ValueError: If `lexeme` carries more than one sense --
            normalize() never builds one, and staging silently
            dropping extras would be a data-loss bug.
    """
    if len(lexeme.senses) > 1:
        msg = (
            f"lexeme {lexeme.natural_key} has {len(lexeme.senses)} "
            "senses; staging assumes at most one"
        )
        raise ValueError(msg)
    sense = lexeme.senses[0] if lexeme.senses else None
    return (
        lexeme.lang_code,
        lexeme.headword,
        lexeme.etymology_number,
        lexeme.romanization,
        lexeme.is_reconstructed,
        lexeme.is_redlink,
        lexeme.source_ref,
        sense.pos if sense else None,
        sense.gloss if sense else None,
        sense is not None,
    )


def _edge_stage_row(edge: EtymEdge) -> tuple[object, ...]:
    return (
        edge.src.lang_code,
        edge.src.headword,
        edge.src.etymology_number,
        edge.dst.lang_code,
        edge.dst.headword,
        edge.dst.etymology_number,
        edge.rel_type.value,
        edge.source_ref,
        edge.piece_order,
    )


def _rebuild_schema(cursor: psycopg.Cursor, schema_sql: str) -> None:
    """Drop and recreate loading from schema.sql and defer its indexes.

    Drops and recreates `loading` from `schema.sql`, then immediately
    drops the five bulk-load-hostile indexes/constraint so COPY and the
    merge inserts that follow hit no index maintenance at all.
    `schema_sql`'s own index DDL builds them once here only to drop them
    immediately; a later bulk-rebuild step recreates them after the
    merge lands.

    Args:
        cursor: Database cursor with an active connection.
        schema_sql: The DDL text from db/schema.sql to execute.
    """
    cursor.execute(f"DROP SCHEMA IF EXISTS {_TARGET_SCHEMA} CASCADE")
    cursor.execute(f"CREATE SCHEMA {_TARGET_SCHEMA}")
    cursor.execute(f"SET search_path TO {_TARGET_SCHEMA}")
    cursor.execute(psycopg.sql.SQL(schema_sql))  # ty: ignore[invalid-argument-type]
    cursor.execute(_STAGING_DDL_SQL)
    cursor.execute(_DROP_DEFERRED_INDEXES_SQL)


def _stage_items(
    database_url: str,
    edges: Iterable[EtymEdge | Lexeme],
    *,
    log_every: int = 100_000,
) -> tuple[int, set[str]]:
    """Stream every edge/lexeme into `loading.stg_lexeme`/`stg_edge`.

    Two connections run one COPY each concurrently: a single
    connection can only have one COPY in flight at a time, and an
    edge's src/dst rows and the edge row itself are written in the
    same pass over `edges` rather than three separate passes (which
    would need `edges` to be re-iterable).

    Args:
        database_url: Postgres connection string.
        edges: The etymology edges to stage, plus any lone lexemes.
        log_every: Emit an INFO progress log every this many items.

    Returns:
        The total item count and the set of distinct language codes
        seen (every code in `stg_lexeme`, since an edge's endpoints
        are always also staged as lexeme rows).
    """
    seen_languages: set[str] = set()
    count = 0
    lex_cols = ", ".join(_LEXEME_STAGE_COLUMNS)
    edge_cols = ", ".join(_EDGE_STAGE_COLUMNS)
    with (
        psycopg.connect(database_url, autocommit=True) as lex_conn,
        psycopg.connect(database_url, autocommit=True) as edge_conn,
        lex_conn.cursor() as lex_cur,
        edge_conn.cursor() as edge_cur,
        lex_cur.copy(
            f"COPY {_TARGET_SCHEMA}.stg_lexeme ({lex_cols}) FROM STDIN"
        ) as lex_copy,
        edge_cur.copy(
            f"COPY {_TARGET_SCHEMA}.stg_edge ({edge_cols}) FROM STDIN"
        ) as edge_copy,
    ):
        for item in edges:
            if isinstance(item, EtymEdge):
                lex_copy.write_row(_lexeme_stage_row(item.src))
                lex_copy.write_row(_lexeme_stage_row(item.dst))
                edge_copy.write_row(_edge_stage_row(item))
                seen_languages.add(item.src.lang_code)
                seen_languages.add(item.dst.lang_code)
            else:
                lex_copy.write_row(_lexeme_stage_row(item))
                seen_languages.add(item.lang_code)
            count += 1
            if count % log_every == 0:
                _log.info("staged %s items", f"{count:,}")
    return count, seen_languages


def load_edges(
    database_url: str,
    edges: Iterable[EtymEdge | Lexeme],
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    checkpoint_path: str | Path | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Upsert edges and their endpoint lexemes into Postgres.

    `edges` also carries a lone Lexeme for any entry `normalize()`
    yielded no edge for (no ancestor-asserting template); that lexeme
    upserts the same way an edge endpoint does, just with no
    etymology row of its own.

    Idempotent: lexemes upsert on their natural key and edges on
    (src_id, dst_id, rel_type), so re-running the same input adds no
    duplicate rows. A failure partway through leaves earlier chunks
    committed rather than rolling back the whole load; safe to re-run.
    Also merges an unnumbered reference stub onto its real, numbered
    sibling once one exists, and clears is_redlink on any lexeme whose
    headword now has a non-redlink sibling from an earlier load,
    regardless of etymology_number.

    Within-run fixups (stub-folding, redlink clearing, degree recompute)
    run once all chunks commit, before the function returns.

    Args:
        database_url: Postgres connection string.
        edges: The etymology edges to load, plus any lone lexemes.
        chunk_size: How many edges to batch and commit at a time.
        checkpoint_path: When given, the count of already-loaded edges and
            this run's start time are read from this path before starting
            (skipping that many edges and reusing that start time) and
            written back after every committed chunk, so a crashed load
            can resume instead of redoing already-committed writes.
        clock: Timestamp source for progress-interval logging. Overridable
            in tests; production code should never pass this.

    Returns:
        The number of items processed (edges and lone lexemes alike),
        including any skipped via a checkpoint from a prior run.
    """
    count, run_started_at = _read_checkpoint(checkpoint_path)
    if run_started_at is None:
        run_started_at = _utcnow()
    if count:
        _log.info("resuming from checkpoint, skipping %s edges", f"{count:,}")
        edges = islice(edges, count, None)

    seen_languages: set[str] = set()
    chunk_was_logged = False
    tick = last_log_time = clock()
    count_at_last_log = count

    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        chunks = _chunked(edges, chunk_size)
        chunk_index = 0
        while True:
            try:
                chunk = next(chunks)
            except StopIteration:
                break
            except Exception:
                _log.error(
                    "chunk %d failed, %d edges in flight", chunk_index, count
                )
                raise

            try:
                count += _load_chunk(
                    cursor, chunk, seen_languages, run_started_at
                )
            except Exception:
                _log.error(
                    "chunk %d failed, %d edges in flight",
                    chunk_index,
                    count + len(chunk),
                )
                raise
            connection.commit()
            _write_checkpoint(checkpoint_path, count, run_started_at)

            tick = clock()
            elapsed = tick - last_log_time
            chunk_was_logged = (
                chunk_index == 0 or elapsed >= _PROGRESS_INTERVAL_SECONDS
            )
            if chunk_was_logged:
                _log_progress(count, count_at_last_log, elapsed)
                last_log_time = tick
                count_at_last_log = count
            chunk_index += 1

        if chunk_index and not chunk_was_logged:
            _log_progress(count, count_at_last_log, tick - last_log_time)

        _merge_split_stub_lexemes(cursor)
        _clear_stale_redlinks(cursor)
        _recompute_degree(cursor)
        connection.commit()

    return count


def _rebuild_indexes(cursor: psycopg.Cursor) -> None:
    """Build every index/constraint Task 3 dropped, in bulk.

    `maintenance_work_mem` is bumped for this session only (ETYM-188
    measured 14.1s for all four lexeme indexes at 1GB, against a
    default of 64MB).
    """
    cursor.execute(_REBUILD_INDEXES_SQL)


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


def _clear_stale_redlinks(cursor: psycopg.Cursor) -> None:
    """Clear a headword's redlink once a real entry exists for it.

    The per-chunk upsert's AND-latch only fires when a real entry
    shares the exact natural key, so a headword split by
    etymology_number (multiple numbered entries, no unnumbered one)
    never collides with its own unnumbered redlink stub.
    """
    cursor.execute(_CLEAR_STALE_REDLINKS_SQL)


def _log_progress(count: int, count_at_last_log: int, elapsed: float) -> None:
    rate = int((count - count_at_last_log) / elapsed) if elapsed > 0 else 0
    _log.info("loaded %s edges (%s edges/sec)", f"{count:,}", f"{rate:,}")


def _read_checkpoint(
    path: str | Path | None,
) -> tuple[int, datetime | None]:
    if path is None:
        return 0, None
    checkpoint = Path(path)
    try:
        raw = checkpoint.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0, None
    payload = json.loads(raw)
    return payload["count"], datetime.fromisoformat(payload["run_started_at"])


def _write_checkpoint(
    path: str | Path | None, count: int, run_started_at: datetime
) -> None:
    if path is None:
        return
    payload = {"count": count, "run_started_at": run_started_at.isoformat()}
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


def _chunked(
    edges: Iterable[EtymEdge | Lexeme], size: int
) -> Iterator[list[EtymEdge | Lexeme]]:
    it = iter(edges)
    while batch := list(islice(it, size)):
        yield batch


def _load_chunk(
    cursor: psycopg.Cursor,
    chunk: list[EtymEdge | Lexeme],
    # kept for legacy chunked upsert path (ARG001 suppressed below)
    seen_languages: set[str],  # ruff: ignore[unused-function-argument]
    run_started_at: datetime,
) -> int:
    with cursor.connection.pipeline():
        lexemes = _unique_lexemes(chunk)
        ids = _upsert_lexemes(
            cursor, [_lexeme_row(lex, run_started_at) for lex in lexemes]
        )
        id_by_lexeme = dict(zip(lexemes, ids, strict=True))

        sense_rows = [
            (
                id_by_lexeme[lexeme],
                sense.pos,
                sense.gloss,
                sense.source_ref,
                run_started_at,
            )
            for lexeme in lexemes
            for sense in lexeme.senses
        ]
        if sense_rows:
            cursor.executemany(_SENSE_UPSERT_SQL, sense_rows, returning=True)

        edge_rows = [
            (
                id_by_lexeme[item.src],
                id_by_lexeme[item.dst],
                item.rel_type.value,
                item.source_ref,
                item.piece_order,
                run_started_at,
            )
            for item in chunk
            if isinstance(item, EtymEdge)
        ]
        if edge_rows:
            cursor.executemany(_EDGE_UPSERT_SQL, edge_rows, returning=True)
    return len(chunk)


def _unique_lexemes(chunk: Iterable[EtymEdge | Lexeme]) -> list[Lexeme]:
    """Distinct lexemes referenced by `chunk`, in first-seen order.

    Multiple edges in a chunk often share an endpoint (a common ancestor
    borrowed into many descendants, or one entry's several templates all
    pointing back at the same descendant); deduping here means each
    distinct lexeme is upserted once per chunk instead of once per edge.
    A lone lexeme (an entry with no edges of its own) is its own
    endpoint.

    Returns:
        The distinct lexemes referenced by `chunk`, in first-seen order.
    """
    unique: dict[Lexeme, None] = {}
    for item in chunk:
        if isinstance(item, EtymEdge):
            unique[item.src] = None
            unique[item.dst] = None
        else:
            unique[item] = None
    return list(unique)


def _lexeme_row(lexeme: Lexeme, run_started_at: datetime) -> tuple[object, ...]:
    return (
        lexeme.lang_code,
        lexeme.headword,
        lexeme.etymology_number,
        lexeme.romanization,
        lexeme.is_reconstructed,
        lexeme.is_redlink,
        lexeme.source_ref,
        run_started_at,
    )


def _upsert_lexemes(
    cursor: psycopg.Cursor, rows: list[tuple[object, ...]]
) -> list[UUID]:
    """Upsert lexemes, returning their ids in the same order as `rows`.

    Returns:
        The upserted ids, one per row, in `rows` order.

    Raises:
        RuntimeError: If any upsert returns no id.
    """
    cursor.executemany(_LEXEME_UPSERT_SQL, rows, returning=True)
    ids: list[UUID] = []
    while True:
        row = cursor.fetchone()
        if row is None:
            msg = "lexeme upsert returned no id"
            raise RuntimeError(msg)
        ids.append(row[0])
        if not cursor.nextset():
            break
    return ids
