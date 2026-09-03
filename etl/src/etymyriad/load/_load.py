"""The public blue/green reload orchestrator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg

from etymyriad.load._fixups import _fixup_and_index
from etymyriad.load._merge import _merge_staged_data
from etymyriad.load._schema import (
    _TARGET_SCHEMA,
    _acquire_load_lock_or_raise,
    _check_pg_trgm_migrated,
    _rebuild_schema,
    _set_search_path_or_raise,
)
from etymyriad.load._staging import _stage_items
from etymyriad.load._swap import _swap_schemas

if TYPE_CHECKING:
    from collections.abc import Iterable

    from etymyriad.model import EtymEdge, Lexeme

_log = logging.getLogger(__name__)

_SCHEMA_SQL_PATH = Path(__file__).resolve().parents[4] / "db" / "schema.sql"


def load_edges(
    database_url: str,
    edges: Iterable[EtymEdge | Lexeme],
    *,
    log_every: int = 100_000,
) -> int:
    """Run the blue/green reload pipeline.

    Builds `loading` from scratch, merges `edges` into it, indexes and
    fixes up what landed, then swaps it in for `public`. Every run
    rebuilds the whole graph from `edges` and replaces `public`
    outright; there is no cross-run state, so a run that fails before
    the final swap leaves `public` exactly as it was. A Postgres
    advisory lock, held for the whole run, rejects a second concurrent
    call rather than letting it race the first run's `loading` schema.

    Args:
        database_url: Postgres connection string.
        edges: The etymology edges to load, plus any lone lexemes.
        log_every: Emit an INFO progress log every this many staged
            items.

    Returns:
        The number of items staged (edges and lone lexemes alike).

    Raises:
        ValueError: If a staged lexeme carries more than one sense, or
            if `edges` yielded nothing at all, since an empty graph is
            never a legitimate thing to swap into `public`.
    """
    schema_sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    with psycopg.connect(database_url, autocommit=True) as lock_connection:
        _acquire_load_lock_or_raise(lock_connection.cursor())

        with psycopg.connect(database_url, autocommit=True) as connection:
            cursor = connection.cursor()
            _check_pg_trgm_migrated(cursor)
            _rebuild_schema(cursor, schema_sql)

        count, seen_languages = _stage_items(
            database_url, edges, log_every=log_every
        )
        if count == 0:
            msg = "refusing to swap an empty graph into public (0 items staged)"
            raise ValueError(msg)
        _log_progress(count)

        with psycopg.connect(database_url, autocommit=True) as connection:
            cursor = connection.cursor()
            _set_search_path_or_raise(cursor, _TARGET_SCHEMA)
            _merge_staged_data(cursor, seen_languages)
            _fixup_and_index(cursor)
            _swap_schemas(connection)
    return count


def _log_progress(count: int) -> None:
    _log.info("staged %s items", f"{count:,}")
