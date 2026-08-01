#!/usr/bin/env python3
"""ETYM-96: merge senseless bound-morpheme lexeme stubs.

`_referenced_lexeme` in normalize.py intentionally builds every
etymology-template reference (ancestor or same-language mention) with
etymology_number=None and no senses -- correct for a genuine cross-
language ancestor mention, since a template's inline gloss describes
one etymology's sense, not the ancestor's own canonical first sense.

But when the referenced term is a same-language bound morpheme that
also has its own dictionary entry with numbered etymologies (e.g. en
"con" referenced as a prefix/affix piece in conjoin, contour, ex-con),
the reference permanently collapses onto its own etym_key='' natural
key instead of the real numbered lexeme -- a stub that gains no senses
no matter how many times the loader re-runs.

This script finds every lexeme with no etymology_number and no senses
that shares (lang_code, headword) with exactly one numbered sibling,
and merges it into that sibling: repointing its edges, then deleting
the stub. A stub matching zero numbered siblings is a genuine bound
morpheme with no entry of its own (most etym_key='' rows -- foreign
ancestor mentions, roots with no own Wiktionary page) and is left
alone. A stub matching more than one numbered sibling is ambiguous --
the template gives no way to tell which numbered etymology it means --
and is also left alone, reported rather than guessed at.

Runs as a dry run by default: it always executes inside a transaction
and only commits with --execute; otherwise it prints the plan and
rolls back.

Usage:
  `./etl/scripts/backfill_bound_morpheme_stubs.py`             # dry run
  `./etl/scripts/backfill_bound_morpheme_stubs.py --execute`   # apply
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


@dataclass(frozen=True, slots=True)
class Stats:
    """Outcome tally for one backfill run.

    Attributes:
        merged: Stubs repointed onto their one numbered sibling and
            deleted.
        ambiguous: Stubs left untouched, matching more than one
            numbered sibling.
    """

    merged: int = 0
    ambiguous: int = 0


class _Outcome(StrEnum):
    """Which of the two ways one stub lexeme was resolved."""

    MERGED = "merged"
    AMBIGUOUS = "ambiguous"


def _find_stub_lexemes(
    cursor: psycopg.Cursor,
) -> list[tuple[str, str, str]]:
    """Return every senseless stub matching at least one numbered sibling.

    A stub is a lexeme with no etymology_number and no senses; only
    those sharing (lang_code, headword) with a numbered sibling are
    candidates for this backfill -- a stub with no such sibling is a
    genuine bound morpheme with no entry of its own.

    Returns:
        (id, lang_code, headword) rows, id as text.
    """
    cursor.execute("""
        SELECT l.id::text, l.lang_code, l.headword
        FROM lexeme l
        WHERE l.etymology_number IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM sense s WHERE s.lexeme_id = l.id
          )
          AND EXISTS (
              SELECT 1 FROM lexeme sib
              WHERE sib.lang_code = l.lang_code
                AND sib.headword = l.headword
                AND sib.etymology_number IS NOT NULL
          )
        ORDER BY l.lang_code, l.headword
    """)
    return cursor.fetchall()


def _find_numbered_siblings(
    cursor: psycopg.Cursor, lang_code: str, headword: str
) -> list[str]:
    """Find numbered-entry candidates for a stub's (lang_code, headword).

    Returns:
        Matching lexeme ids (as text), 1 or more.
    """
    cursor.execute(
        "SELECT id::text FROM lexeme WHERE lang_code = %s AND headword = %s "
        "AND etymology_number IS NOT NULL",
        (lang_code, headword),
    )
    return [row[0] for row in cursor.fetchall()]


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
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
        SELECT %(target)s, dst_id, rel_type, source_ref
        FROM etymology
        WHERE src_id = %(old)s AND dst_id <> %(target)s
        ON CONFLICT (src_id, dst_id, rel_type) DO NOTHING
        """,
        {"target": target_id, "old": old_id},
    )
    cursor.execute("DELETE FROM etymology WHERE src_id = %s", (old_id,))
    cursor.execute(
        """
        INSERT INTO etymology (src_id, dst_id, rel_type, source_ref)
        SELECT src_id, %(target)s, rel_type, source_ref
        FROM etymology
        WHERE dst_id = %(old)s AND src_id <> %(target)s
        ON CONFLICT (src_id, dst_id, rel_type) DO NOTHING
        """,
        {"target": target_id, "old": old_id},
    )
    cursor.execute("DELETE FROM etymology WHERE dst_id = %s", (old_id,))


def _resolve_stub_lexeme(
    cursor: psycopg.Cursor, old_id: str, lang_code: str, headword: str
) -> _Outcome:
    """Merge one stub into its numbered sibling, or flag it as ambiguous.

    Args:
        cursor: An open cursor inside the run's transaction.
        old_id: The stub lexeme's id.
        lang_code: The stub lexeme's language code.
        headword: The stub lexeme's headword.

    Returns:
        Which of the two outcomes this stub resolved to.
    """
    candidates = _find_numbered_siblings(cursor, lang_code, headword)

    if len(candidates) > 1:
        _log.warning(
            "ambiguous: %s/%s matches %d numbered siblings, skipping",
            lang_code,
            headword,
            len(candidates),
        )
        return _Outcome.AMBIGUOUS

    target_id = candidates[0]
    _log.info("merge: %s/%s -> %s", lang_code, headword, target_id)
    _repoint_edges(cursor, old_id, target_id)
    cursor.execute("DELETE FROM lexeme WHERE id = %s", (old_id,))
    return _Outcome.MERGED


def backfill(database_url: str, *, execute: bool) -> Stats:
    """Merge or flag every senseless bound-morpheme stub on `database_url`.

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
            _resolve_stub_lexeme(cursor, old_id, lang_code, headword)
            for old_id, lang_code, headword in stubs
        )

        if execute:
            connection.commit()
        else:
            connection.rollback()

    stats = Stats(
        merged=outcomes[_Outcome.MERGED],
        ambiguous=outcomes[_Outcome.AMBIGUOUS],
    )
    _log.info(
        "%s: merged=%d ambiguous=%d",
        "applied" if execute else "dry run (rolled back)",
        stats.merged,
        stats.ambiguous,
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
