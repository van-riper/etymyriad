"""Stream edges and terms into the staging tables via COPY."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import psycopg

from etymyriad.load._schema import _TARGET_SCHEMA
from etymyriad.model import EtymEdge

if TYPE_CHECKING:
    from collections.abc import Iterable

    from etymyriad.model import Term

_log = logging.getLogger(__name__)

_TERM_STAGE_COLUMNS = (
    "lang_code",
    "headword",
    "section",
    "is_reconstructed",
    "part_of_speech",
    "gloss",
    "has_sense",
)
_EDGE_STAGE_COLUMNS = (
    "src_lang_code",
    "src_headword",
    "src_section",
    "src_variety_code",
    "dst_lang_code",
    "dst_headword",
    "dst_section",
    "rel_type",
    "anchor",
    "piece_order",
)


def _term_stage_row(term: Term) -> tuple[object, ...]:
    """Flatten a term occurrence plus its at-most-one sense.

    Empty part_of_speech/gloss strings become None, so the merge's
    DISTINCT never splits one sense into two rows.

    Returns:
        A tuple in `_TERM_STAGE_COLUMNS` order.

    Raises:
        ValueError: If `term` carries more than one sense; normalize
            never builds one, and dropping extras would lose data.
    """
    if len(term.senses) > 1:
        msg = (
            f"term {term.key} has {len(term.senses)} senses; "
            "staging assumes at most one"
        )
        raise ValueError(msg)
    sense = term.senses[0] if term.senses else None
    return (
        term.lang_code,
        term.headword,
        term.section,
        term.is_reconstructed,
        (sense.part_of_speech or None) if sense else None,
        (sense.gloss or None) if sense else None,
        sense is not None,
    )


def _edge_stage_row(edge: EtymEdge) -> tuple[object, ...]:
    """Flatten an edge into its staging table's column order.

    Returns:
        A tuple in `_EDGE_STAGE_COLUMNS` order.
    """
    return (
        edge.src.lang_code,
        edge.src.headword,
        edge.src.section,
        edge.src.variety_code,
        edge.dst.lang_code,
        edge.dst.headword,
        edge.dst.section,
        edge.rel_type.value,
        edge.anchor,
        edge.piece_order,
    )


def _codes_of(term: Term) -> tuple[str, ...]:
    """Return the term's language code plus its variety code when set."""
    if term.variety_code is None:
        return (term.lang_code,)
    return (term.lang_code, term.variety_code)


def _stage_items(
    database_url: str,
    edges: Iterable[EtymEdge | Term],
    *,
    log_every: int = 100_000,
) -> tuple[int, set[str]]:
    """Stream every edge/term into `loading.stg_term`/`stg_edge`.

    Two connections run one COPY each concurrently: a single
    connection can only have one COPY in flight at a time, and an
    edge's src/dst rows and the edge row itself are written in the
    same pass over `edges` rather than three separate passes (which
    would need `edges` to be re-iterable).

    Args:
        database_url: Postgres connection string.
        edges: The etymology edges to stage, plus any lone terms.
        log_every: Emit an INFO progress log every this many items.

    Returns:
        The item count and every language and variety code the items
        name.
    """
    seen_codes: set[str] = set()
    count = 0
    started_seconds = time.monotonic()
    term_cols = ", ".join(_TERM_STAGE_COLUMNS)
    edge_cols = ", ".join(_EDGE_STAGE_COLUMNS)

    with (
        psycopg.connect(database_url, autocommit=True) as term_conn,
        psycopg.connect(database_url, autocommit=True) as edge_conn,
        term_conn.cursor() as term_cur,
        edge_conn.cursor() as edge_cur,
        term_cur.copy(
            f"COPY {_TARGET_SCHEMA}.stg_term ({term_cols}) FROM STDIN"
        ) as term_copy,
        edge_cur.copy(
            f"COPY {_TARGET_SCHEMA}.stg_edge ({edge_cols}) FROM STDIN"
        ) as edge_copy,
    ):
        for item in edges:
            if isinstance(item, EtymEdge):
                term_copy.write_row(_term_stage_row(item.src))
                term_copy.write_row(_term_stage_row(item.dst))
                edge_copy.write_row(_edge_stage_row(item))
                seen_codes.update(_codes_of(item.src))
                seen_codes.update(_codes_of(item.dst))
            else:
                term_copy.write_row(_term_stage_row(item))
                seen_codes.update(_codes_of(item))
            count += 1
            if count % log_every == 0:
                items_per_second = count / (time.monotonic() - started_seconds)
                _log.info(
                    "staged %s items (%s/sec)",
                    f"{count:,}",
                    f"{items_per_second:,.0f}",
                )
    return count, seen_codes
