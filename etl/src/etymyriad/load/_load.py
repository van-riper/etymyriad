"""The public blue/green reload orchestrator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg

from etymyriad.load._finalize import (
    _build_indexes,
    _check_drift_or_raise,
    _check_unknown_languages_or_raise,
    _fill_pickable_terms,
    _vacuum_analyze,
)
from etymyriad.load._merge import _merge_staged_data
from etymyriad.load._schema import (
    _TARGET_SCHEMA,
    _acquire_load_lock_or_raise,
    _rebuild_schema,
    _set_search_path_or_raise,
)
from etymyriad.load._staging import _stage_items
from etymyriad.load._swap import _swap_schemas

if TYPE_CHECKING:
    from collections.abc import Iterable

    from etymyriad.model import GraphItem

_log = logging.getLogger(__name__)

_SCHEMA_SQL_PATH = Path(__file__).resolve().parents[4] / "db" / "schema.sql"


def load_edges(
    database_url: str,
    edges: Iterable[GraphItem],
    *,
    dump_date: str,
    check_drift: bool = True,
    log_every: int = 100_000,
) -> int:
    """Run the blue/green reload pipeline.

    Builds `loading` from scratch, merges `edges` into it, indexes and
    gates what landed, then swaps it in for `public`, dropping the old
    generation. Every run rebuilds the whole graph from `edges`; there
    is no cross-run state, so a run that fails before the swap leaves
    `public` exactly as it was and drops its own `loading` schema. A
    Postgres advisory lock, held for the whole run, rejects a second
    concurrent call rather than letting it race the first run's
    `loading` schema. An empty `edges` raises `ValueError`, since an
    empty graph is never worth swapping into `public`.

    Args:
        database_url: Postgres connection string.
        edges: The etymology edges to load, plus any lone terms and
            section claims.
        dump_date: The Wiktextract dump date every `source_ref` cites.
        check_drift: Refuse to swap when the term or edge count moved
            more than 10% from `public`.
        log_every: Emit an INFO progress log every this many staged
            items.

    Returns:
        The number of items staged (edges and lone terms alike).
    """
    with psycopg.connect(database_url, autocommit=True) as lock_connection:
        _acquire_load_lock_or_raise(lock_connection.cursor())

        try:
            count = _build_and_swap(
                database_url,
                edges,
                dump_date=dump_date,
                check_drift=check_drift,
                log_every=log_every,
            )
        except BaseException:
            try:
                _drop_loading_schema(database_url)
            except (psycopg.Error, OSError):
                _log.exception("could not drop the loading schema")
            raise
    return count


def _build_and_swap(
    database_url: str,
    edges: Iterable[GraphItem],
    *,
    dump_date: str,
    check_drift: bool,
    log_every: int,
) -> int:
    """Rebuild, stage, merge, finalize, gate, and swap `loading`.

    Returns:
        The number of items staged.

    Raises:
        ValueError: If `edges` yielded nothing.
    """
    schema_sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    with psycopg.connect(database_url, autocommit=True) as connection:
        _rebuild_schema(connection.cursor(), schema_sql)

    count, seen_codes = _stage_items(database_url, edges, log_every=log_every)
    if count == 0:
        msg = "refusing to swap an empty graph into public (0 items staged)"
        raise ValueError(msg)
    _log_progress(count)

    with psycopg.connect(database_url, autocommit=True) as connection:
        cursor = connection.cursor()
        _set_search_path_or_raise(cursor, _TARGET_SCHEMA)
        counts = _merge_staged_data(cursor, seen_codes, dump_date)
        _check_unknown_languages_or_raise(counts)
        _build_indexes(cursor)
        _fill_pickable_terms(cursor)
        _vacuum_analyze(connection)
        if check_drift:
            _check_drift_or_raise(cursor)
        _swap_schemas(connection)
    return count


def _drop_loading_schema(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(f"DROP SCHEMA IF EXISTS {_TARGET_SCHEMA} CASCADE")


def _log_progress(count: int) -> None:
    _log.info("staged %s items", f"{count:,}")
