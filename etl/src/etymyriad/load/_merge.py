"""Resolve staged natural keys into lexeme/sense/etymology rows."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from etymyriad.languages import language_family, language_name
from etymyriad.model import PROTO_LANG_SUFFIX

if TYPE_CHECKING:
    from collections.abc import Iterable

    import psycopg

_log = logging.getLogger(__name__)

# A plain INSERT, no ON CONFLICT: `loading.language` is empty every
# run and the codes arrive already deduplicated, so nothing can
# conflict.
_LANGUAGE_INSERT_SQL = """
    INSERT INTO language (code, name, lang_family, is_proto)
    VALUES (%s, %s, %s, %s)
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


def _merge_staged_data(
    cursor: psycopg.Cursor, seen_languages: Iterable[str]
) -> None:
    """Resolve staged natural keys into lexeme/sense/etymology rows.

    Fills the `language` table first, since every lexeme row references
    it. Then aggregates every staged occurrence of a natural key in one
    pass: `is_reconstructed` OR-latches, `is_redlink` AND-latches, and
    `romanization`/`source_ref` take any non-null value (both are
    deterministic per natural key within one run's dump, so any
    occurrence's value is as good as any other's). Drops the staging
    tables once resolved, so they never survive into `public`.

    Args:
        cursor: Database cursor with an active connection; search_path
            must be set to `loading`.
        seen_languages: Language codes encountered during staging.
    """
    codes = sorted(seen_languages)
    _log.debug("inserting %d language(s): %s", len(codes), codes)
    cursor.executemany(
        _LANGUAGE_INSERT_SQL,
        [
            (
                code,
                language_name(code) or code,
                language_family(code),
                code.endswith(PROTO_LANG_SUFFIX),
            )
            for code in codes
        ],
    )
    cursor.execute(_MERGE_LEXEMES_SQL)
    cursor.execute(_MERGE_SENSES_SQL)
    cursor.execute(_MERGE_EDGES_SQL)
    cursor.execute(_DROP_STAGING_SQL)
