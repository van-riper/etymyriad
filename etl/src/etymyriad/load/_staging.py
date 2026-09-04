"""Stream edges and lexemes into the staging tables via COPY."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import psycopg

from etymyriad.load._schema import _TARGET_SCHEMA
from etymyriad.model import EtymEdge

if TYPE_CHECKING:
    from collections.abc import Iterable

    from etymyriad.model import Lexeme

_log = logging.getLogger(__name__)

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


def _lexeme_stage_row(lexeme: Lexeme) -> tuple[object, ...]:
    """Flatten a lexeme occurrence, plus its at-most-one sense.

    `etymology_number`/`pos`/`gloss` coerce an empty string to None:
    each one's generated key column COALESCEs it to '', so the unique
    index treats the two as the same value while the merge's own
    GROUP BY/DISTINCT would split them into rows that then collide.

    Returns:
        A tuple of (lang_code, headword, etymology_number, romanization,
            is_reconstructed, is_redlink, source_ref, pos, gloss,
            has_sense).

    Raises:
        ValueError: If `lexeme` carries more than one sense:
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
        lexeme.etymology_number or None,
        lexeme.romanization,
        lexeme.is_reconstructed,
        lexeme.is_redlink,
        lexeme.source_ref,
        (sense.pos or None) if sense else None,
        (sense.gloss or None) if sense else None,
        sense is not None,
    )


def _edge_stage_row(edge: EtymEdge) -> tuple[object, ...]:
    """Flatten an edge into its staging table's column order.

    Returns:
        A tuple of (src_lang_code, src_headword, src_etymology_number,
            dst_lang_code, dst_headword, dst_etymology_number, rel_type,
            source_ref, piece_order).
    """
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
