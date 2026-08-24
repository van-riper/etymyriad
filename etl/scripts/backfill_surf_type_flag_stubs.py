#!/usr/bin/env python3
"""Merge {{surf}} "+type"-flag lexeme stubs onto their real language.

`normalize.py`'s affix-family parsing now reads {{surf}}'s optional
leading "+type" flag (e.g. "+suf", "+deverbal") as the annotation it
is, instead of mistaking it for the ancestor pieces' language -- but
that fix only applies to future loads. Every row already loaded before
it still carries the flag string as its own bogus "language" (e.g.
lang_code="+suf"), with its pieces keyed on that flag instead of the
real ancestor language.

For a stub whose flag names a real formation type ("+suf",
"+deverbal", "+it-deverbal", ...), the real language is the single
language shared by every entry that cites it (a stub's citing entries
are its edges' dst side). A stub cited by more than one distinct
language is ambiguous -- SQL has no way to tell which citing edge
means which language -- and is left untouched, reported rather than
guessed at.

Two flags, "+onom" and "+lit", never carry a real morpheme piece at
all (confirmed by hand against every occurrence in the local full
load): {{surf|+onom|<lang>}} classifies a word as onomatopoeic with no
pieces, and {{surf|+lit|<gloss>}} glosses a phrase literally -- the old
parsing mistook the language argument and the gloss, respectively, for
a piece. Both are dropped outright rather than merged or renamed: like
a literal "-" term placeholder, there is no real term to redirect a
drop onto.

Known limitation: a generic flag can, rarely, name a citing language
different from the entry that names it (e.g. a modern Polish entry
citing an Old Polish morpheme via {{surf|+deverbal|zlw-opl|...}}). A
stub's lexeme row carries no record of the citing template's own
language argument, only of the entries that reference it, so this is
indistinguishable from the ordinary same-language case when the stub
is cited by only that one entry -- it renames onto the citing entry's
own language, which is usually but not always correct. Confirmed rare
(single digits) against the local full load; resolving it exactly
would need re-parsing the raw dump, not justified for that few rows.

Runs as a dry run by default: it always executes inside a transaction
and only commits with --execute; otherwise it prints the plan and
rolls back.

Usage:
  `./etl/scripts/backfill_surf_type_flag_stubs.py`             # dry run
  `./etl/scripts/backfill_surf_type_flag_stubs.py --execute`   # apply
"""

from __future__ import annotations

import argparse
import logging
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

import psycopg

from etymyriad.config import Config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger(__name__)

# {{surf}} "+type" flags confirmed (against the local full load) to
# never carry a real morpheme piece -- the old parsing's one "piece"
# for these was actually the citing entry's own language ("+onom") or
# a multi-word gloss ("+lit"), never an attested term.
_NO_PIECE_FLAGS = frozenset({"+onom", "+lit"})


@dataclass(frozen=True, slots=True)
class Stats:
    """Outcome tally for one backfill run.

    Attributes:
        dropped: "+onom"/"+lit" stubs deleted outright, with their
            edges.
        merged: Stubs repointed onto an existing real node and deleted.
        renamed: Stubs renamed in place (no real node existed yet).
        ambiguous: Stubs left untouched, cited by more than one
            language.
        unsafe: Stubs left untouched, carrying their own sense rows.
    """

    dropped: int = 0
    merged: int = 0
    renamed: int = 0
    ambiguous: int = 0
    unsafe: int = 0


class _Outcome(StrEnum):
    """Which of the five ways one stub lexeme was resolved."""

    DROPPED = "dropped"
    MERGED = "merged"
    RENAMED = "renamed"
    AMBIGUOUS = "ambiguous"
    UNSAFE = "unsafe"


def _find_stub_lexemes(
    cursor: psycopg.Cursor,
) -> list[tuple[str, str, str, str]]:
    """Return every lexeme keyed on a {{surf}} "+type" flag as its language.

    Returns:
        (id, flag, headword, source_ref) rows, id as text.
    """
    cursor.execute(
        "SELECT id::text, lang_code, headword, source_ref FROM lexeme "
        "WHERE lang_code LIKE '+%%' ORDER BY lang_code, headword"
    )
    return cursor.fetchall()


def _citing_languages(cursor: psycopg.Cursor, stub_id: str) -> list[str]:
    """Return the distinct languages of every entry citing this stub.

    Returns:
        Distinct dst.lang_code values across the stub's edges.
    """
    cursor.execute(
        "SELECT DISTINCT dst.lang_code FROM etymology e "
        "JOIN lexeme dst ON dst.id = e.dst_id WHERE e.src_id = %s",
        (stub_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def _find_merge_target(
    cursor: psycopg.Cursor, lang_code: str, headword: str
) -> str | None:
    """Find the real-node candidate for a stub's real (lang, headword).

    Returns:
        The matching lexeme id (as text), or None if no real node
        exists yet -- `lexeme_natural_key` guarantees at most one.
    """
    cursor.execute(
        "SELECT id::text FROM lexeme WHERE lang_code = %s AND headword = %s "
        "AND etymology_number IS NULL",
        (lang_code, headword),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _sense_count(cursor: psycopg.Cursor, lexeme_id: str) -> int:
    """Return how many sense rows a lexeme carries."""
    cursor.execute(
        "SELECT count(*) FROM sense WHERE lexeme_id = %s", (lexeme_id,)
    )
    row = cursor.fetchone()
    return 0 if row is None else row[0]


def _repoint_edges(cursor: psycopg.Cursor, old_id: str, target_id: str) -> None:
    """Move every edge touching `old_id` onto `target_id`.

    Inserts the repointed edge first (skipping one that would collide
    with an existing edge under etymology_unique_edge, or collapse
    into a src == dst self-loop now that both ends resolve to
    `target_id`), then drops the original. `old_id`'s row is deleted by
    the caller afterward.
    """
    cursor.execute(
        """
        INSERT INTO etymology
            (src_id, dst_id, rel_type, source_ref, piece_order)
        SELECT %(target)s, dst_id, rel_type, source_ref, piece_order
        FROM etymology
        WHERE src_id = %(old)s AND dst_id <> %(target)s
        ON CONFLICT (src_id, dst_id, rel_type) DO NOTHING
        """,
        {"target": target_id, "old": old_id},
    )
    cursor.execute("DELETE FROM etymology WHERE src_id = %s", (old_id,))
    cursor.execute(
        """
        INSERT INTO etymology
            (src_id, dst_id, rel_type, source_ref, piece_order)
        SELECT src_id, %(target)s, rel_type, source_ref, piece_order
        FROM etymology
        WHERE dst_id = %(old)s AND src_id <> %(target)s
        ON CONFLICT (src_id, dst_id, rel_type) DO NOTHING
        """,
        {"target": target_id, "old": old_id},
    )
    cursor.execute("DELETE FROM etymology WHERE dst_id = %s", (old_id,))


def _drop_stub(cursor: psycopg.Cursor, stub_id: str) -> None:
    """Delete a stub lexeme and every edge pointing into it."""
    cursor.execute(
        "DELETE FROM etymology WHERE src_id = %(id)s OR dst_id = %(id)s",
        {"id": stub_id},
    )
    cursor.execute("DELETE FROM lexeme WHERE id = %s", (stub_id,))


def _rename_stub(
    cursor: psycopg.Cursor, stub_id: str, lang_code: str, source_ref: str
) -> None:
    """Rename a stub in place onto its real language.

    `source_ref` (`wiktionary:<date>:<flag>:<headword>`) is rebuilt with
    only the flag segment replaced, so provenance still points at the
    real dump date and headword.
    """
    _, date, _, headword = source_ref.split(":", 3)
    cursor.execute(
        "UPDATE lexeme SET lang_code = %s, source_ref = %s WHERE id = %s",
        (lang_code, f"wiktionary:{date}:{lang_code}:{headword}", stub_id),
    )


def _resolve_stub_lexeme(
    cursor: psycopg.Cursor,
    stub_id: str,
    flag: str,
    headword: str,
    source_ref: str,
) -> _Outcome:
    """Drop, merge, rename, or flag one stub lexeme as unresolved.

    Args:
        cursor: An open cursor inside the run's transaction.
        stub_id: The stub lexeme's id.
        flag: The stub's bogus lang_code -- the original "+type" flag.
        headword: The stub lexeme's headword.
        source_ref: The stub lexeme's stored source_ref.

    Returns:
        Which of the five outcomes this stub resolved to.
    """
    if flag in _NO_PIECE_FLAGS:
        _log.info("drop: %s/%s (no real morpheme piece)", flag, headword)
        _drop_stub(cursor, stub_id)
        return _Outcome.DROPPED

    citing_languages = _citing_languages(cursor, stub_id)
    if len(citing_languages) != 1:
        _log.warning(
            "ambiguous: %s/%s cited by %d language(s), skipping",
            flag,
            headword,
            len(citing_languages),
        )
        return _Outcome.AMBIGUOUS

    lang_code = citing_languages[0]
    target_id = _find_merge_target(cursor, lang_code, headword)

    if target_id is None:
        _log.info("rename: %s/%s -> %s/%s", flag, headword, lang_code, headword)
        _rename_stub(cursor, stub_id, lang_code, source_ref)
        return _Outcome.RENAMED

    if _sense_count(cursor, stub_id) > 0:
        _log.warning(
            "unsafe: %s/%s carries its own senses, skipping", flag, headword
        )
        return _Outcome.UNSAFE

    _log.info("merge: %s/%s -> %s/%s", flag, headword, lang_code, headword)
    _repoint_edges(cursor, stub_id, target_id)
    cursor.execute("DELETE FROM lexeme WHERE id = %s", (stub_id,))
    return _Outcome.MERGED


def backfill(database_url: str, *, execute: bool) -> Stats:
    """Resolve every {{surf}} "+type"-flag stub found on `database_url`.

    Args:
        database_url: Postgres connection string.
        execute: Commit the transaction if True; roll it back (dry
            run) if False.

    Returns:
        The run's outcome tally.
    """
    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        stubs = _find_stub_lexemes(cursor)
        _log.info("found %d candidate stub(s)", len(stubs))

        outcomes = Counter(
            _resolve_stub_lexeme(cursor, stub_id, flag, headword, source_ref)
            for stub_id, flag, headword, source_ref in stubs
        )

        if execute:
            connection.commit()
        else:
            connection.rollback()

    stats = Stats(
        dropped=outcomes[_Outcome.DROPPED],
        merged=outcomes[_Outcome.MERGED],
        renamed=outcomes[_Outcome.RENAMED],
        ambiguous=outcomes[_Outcome.AMBIGUOUS],
        unsafe=outcomes[_Outcome.UNSAFE],
    )
    _log.info(
        "%s: dropped=%d merged=%d renamed=%d ambiguous=%d unsafe=%d",
        "applied" if execute else "dry run (rolled back)",
        stats.dropped,
        stats.merged,
        stats.renamed,
        stats.ambiguous,
        stats.unsafe,
    )
    return stats


def main() -> int:
    """Parse args and run the backfill.

    Returns:
        0 on success (the process exit code).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="commit the changes (default: dry run, rolled back)",
    )
    args = parser.parse_args()

    config = Config.from_env()
    backfill(config.database_url, execute=args.execute)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
