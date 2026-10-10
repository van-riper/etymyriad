"""Resolve staged natural keys into term, sense, and edge rows."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple

from etymyriad.languages import LanguageKind, resolve_language

if TYPE_CHECKING:
    from collections.abc import Iterable

    import psycopg

_log = logging.getLogger(__name__)

_LANGUAGE_INSERT_SQL = """
    INSERT INTO language (code, name, kind) VALUES (%s, %s, %s)
"""

_VARIETY_INSERT_SQL = """
    INSERT INTO variety (language_id, code, name)
    SELECT id, %s, %s FROM language WHERE code = %s
"""

_DATASET_INSERT_SQL = "INSERT INTO dataset (dump_date) VALUES (%s)"

_COUNT_EDGES_SQL = """
    SELECT count(*),
           count(*) FILTER (WHERE NOT EXISTS (
               SELECT 1 FROM language WHERE code = e.src_lang_code)
           OR NOT EXISTS (
               SELECT 1 FROM language WHERE code = e.dst_lang_code))
    FROM stg_edge AS e
"""

# One row per distinct (lang, headword) staged anywhere, so the alias
# pass and the term insert both read a deduplicated set. A real entry's
# own flag wins over references: a variety's starred citation can name
# a word that has a real page in its full language.
_STAGE_TERM_KEYS_SQL = """
    CREATE UNLOGGED TABLE stg_term_key AS
    SELECT lang_code, headword,
           COALESCE(bool_or(is_reconstructed) FILTER (WHERE has_sense),
                    bool_or(is_reconstructed)) AS is_reconstructed,
           bool_or(has_sense) AS has_sense
    FROM (
        SELECT lang_code, headword, is_reconstructed, has_sense
        FROM stg_term
    ) AS occurrence
    GROUP BY lang_code, headword
"""

# Wiktionary writes a macron or breve over a vowel for the reader, then
# cites the same word without it, so a page gets a diacritic-only
# redlink twin (grc "ἔτῠμον" beside the real "ἔτυμον"). Only those two
# marks are stripped: Greek accents and breathings are combining marks
# too, and stripping them would merge distinct words. Reconstructions
# are exempt, since a proto-form's macron is a claim about vowel length.
# A stub matching more than one real twin is left alone.
_STAGE_ALIASES_SQL = r"""
    CREATE UNLOGGED TABLE stg_alias AS
    SELECT stub.lang_code, stub.headword AS from_headword,
           min(real_term.headword) AS to_headword
    FROM stg_term_key AS stub
    JOIN stg_term_key AS real_term
      ON real_term.lang_code = stub.lang_code
     AND real_term.has_sense
     AND NOT real_term.is_reconstructed
     AND real_term.headword <> stub.headword
     AND translate(normalize(real_term.headword, NFD), U&'\0304\0306', '')
       = translate(normalize(stub.headword, NFD), U&'\0304\0306', '')
    WHERE NOT stub.has_sense
      AND NOT stub.is_reconstructed
      AND normalize(stub.headword, NFD) ~ U&'[\0304\0306]'
    GROUP BY stub.lang_code, stub.headword
    HAVING count(*) = 1
"""

_MERGE_TERMS_SQL = """
    INSERT INTO term (language_id, headword, is_reconstructed)
    SELECT language.id, k.headword, k.is_reconstructed
    FROM stg_term_key AS k
    JOIN language ON language.code = k.lang_code
    WHERE NOT EXISTS (
        SELECT 1 FROM stg_alias AS a
        WHERE a.lang_code = k.lang_code AND a.from_headword = k.headword
    )
"""

_MERGE_SENSES_SQL = """
    INSERT INTO sense (term_id, section, part_of_speech, gloss)
    SELECT DISTINCT term.id, s.section, s.part_of_speech, s.gloss
    FROM stg_term AS s
    JOIN language ON language.code = s.lang_code
    JOIN term ON term.language_id = language.id
             AND term.headword = s.headword
    WHERE s.has_sense
"""

_MERGE_EDGES_SQL = """
    INSERT INTO edge (src_term_id, src_section, dst_term_id, dst_section,
                      rel_type, src_variety_id, anchor, piece_order)
    SELECT DISTINCT ON (src.id, e.src_section, dst.id, e.dst_section,
                        e.rel_type)
           src.id, e.src_section, dst.id, e.dst_section,
           e.rel_type::edge_type, variety.id, e.anchor, e.piece_order
    FROM stg_edge AS e
    JOIN language AS src_language ON src_language.code = e.src_lang_code
    JOIN language AS dst_language ON dst_language.code = e.dst_lang_code
    LEFT JOIN stg_alias AS src_alias
      ON src_alias.lang_code = e.src_lang_code
     AND src_alias.from_headword = e.src_headword
    LEFT JOIN stg_alias AS dst_alias
      ON dst_alias.lang_code = e.dst_lang_code
     AND dst_alias.from_headword = e.dst_headword
    JOIN term AS src
      ON src.language_id = src_language.id
     AND src.headword = COALESCE(src_alias.to_headword, e.src_headword)
    JOIN term AS dst
      ON dst.language_id = dst_language.id
     AND dst.headword = COALESCE(dst_alias.to_headword, e.dst_headword)
    LEFT JOIN variety ON variety.code = e.src_variety_code
    WHERE src.id <> dst.id
    ORDER BY src.id, e.src_section, dst.id, e.dst_section, e.rel_type,
             split_part(e.anchor, ':', 2)::int, e.anchor
"""

_DROP_STAGING_SQL = "DROP TABLE stg_term, stg_edge, stg_term_key, stg_alias"


class MergeCounts(NamedTuple):
    """Edge counts the post-merge gate needs.

    Attributes:
        staged_edges: Rows in stg_edge.
        unknown_language_edges: Staged edges dropped because an end's
            language code isn't in the registry.
    """

    staged_edges: int
    unknown_language_edges: int


type _LanguageRow = tuple[str, str, str]


def _language_rows(
    codes: Iterable[str],
) -> tuple[list[_LanguageRow], list[_LanguageRow]]:
    """Split seen codes into language and variety rows.

    A variety's full language is added even if no term used it
    directly. A code the registry doesn't know gets no row, so the
    merge's joins drop whatever named it.

    Returns:
        (language rows as (code, name, kind), variety rows as
        (code, name, full language code)), each sorted by code.
    """
    languages: dict[str, _LanguageRow] = {}
    varieties: dict[str, _LanguageRow] = {}
    for code in codes:
        language = resolve_language(code)
        if language is None:
            _log.warning("dropping unknown language code %r", code)
            continue
        full_language = language.full_language
        languages[full_language.code] = (
            full_language.code,
            full_language.name,
            full_language.kind.value,
        )
        if language.kind is LanguageKind.VARIETY:
            varieties[language.code] = (
                language.code,
                language.name,
                full_language.code,
            )
    return sorted(languages.values()), sorted(varieties.values())


def _merge_staged_data(
    cursor: psycopg.Cursor, seen_codes: Iterable[str], dump_date: str
) -> MergeCounts:
    """Resolve staged rows into the final tables, inserting each once.

    Args:
        cursor: Cursor whose search_path is `loading`.
        seen_codes: Language and variety codes seen while staging.
        dump_date: The dump's YYYY-MM-DD date, which every citation names.

    Returns:
        The staged edge count and how many were dropped for an unknown
        language code.

    Raises:
        RuntimeError: If the edge count query returns no row.
    """
    language_rows, variety_rows = _language_rows(seen_codes)
    cursor.executemany(_LANGUAGE_INSERT_SQL, language_rows)
    cursor.executemany(_VARIETY_INSERT_SQL, variety_rows)
    cursor.execute(_DATASET_INSERT_SQL, (dump_date,))

    cursor.execute(_COUNT_EDGES_SQL)
    row = cursor.fetchone()
    if row is None:
        msg = "edge count query returned no row"
        raise RuntimeError(msg)
    staged, unknown = row

    for sql in (
        _STAGE_TERM_KEYS_SQL,
        _STAGE_ALIASES_SQL,
        "ANALYZE stg_term_key, stg_alias",
        _MERGE_TERMS_SQL,
        "ANALYZE term",
        _MERGE_SENSES_SQL,
        _MERGE_EDGES_SQL,
        _DROP_STAGING_SQL,
    ):
        cursor.execute(sql)
    return MergeCounts(staged_edges=staged, unknown_language_edges=unknown)
