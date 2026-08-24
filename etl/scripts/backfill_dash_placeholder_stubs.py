#!/usr/bin/env python3
"""Delete literal "-" term-placeholder lexeme stubs.

Wiktionary editors write a literal "-" as a directional template's term
argument (e.g. {{der|en|la|-}}) to assert a language-level derivation
without naming a specific attested term. Before normalize.py's fix,
`_referenced_lexeme` treated "-" as if it were a real headword, so it
became its own lexeme node per language -- a meaningless node named
"-" that accumulated every such "unspecified term" edge for that
language. That fix stops new rows from leaking, but rows already
loaded before it still carry the bogus "-" nodes.

Unlike the other stub-merge backfills, there is no real target to
repoint a "-" node's edges onto -- the template never named an
attested term, so
the edge asserts nothing resolvable. This script deletes each "-"
lexeme and every edge pointing into it outright. A "-" lexeme carrying
its own sense rows is a genuine dictionary entry for the hyphen
character itself, not the parser bug's stub (a bogus reference node
never gets senses -- see `_referenced_lexeme`), and is left untouched.

Runs as a dry run by default: it always executes inside a transaction
and only commits with --execute; otherwise it prints the plan and
rolls back.

Usage:
  `./etl/scripts/backfill_dash_placeholder_stubs.py`             # dry run
  `./etl/scripts/backfill_dash_placeholder_stubs.py --execute`   # apply
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

import psycopg

from etymyriad.config import Config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Stats:
    """Outcome tally for one backfill run.

    Attributes:
        deleted: "-" placeholder lexemes deleted, with their edges.
        unsafe: "-" lexemes left untouched, carrying their own senses.
    """

    deleted: int = 0
    unsafe: int = 0


def _find_dash_placeholder_lexemes(
    cursor: psycopg.Cursor,
) -> list[tuple[str, str]]:
    """Return every lexeme keyed on the literal "-" placeholder headword.

    Returns:
        (id, lang_code) rows, id as text.
    """
    cursor.execute(
        "SELECT id::text, lang_code FROM lexeme WHERE headword = '-' "
        "ORDER BY lang_code"
    )
    return cursor.fetchall()


def _sense_count(cursor: psycopg.Cursor, lexeme_id: str) -> int:
    """Return how many sense rows a lexeme carries."""
    cursor.execute(
        "SELECT count(*) FROM sense WHERE lexeme_id = %s", (lexeme_id,)
    )
    row = cursor.fetchone()
    return 0 if row is None else row[0]


def _delete_dash_placeholder(cursor: psycopg.Cursor, lexeme_id: str) -> None:
    """Delete one "-" lexeme and every edge pointing into it."""
    cursor.execute(
        "DELETE FROM etymology WHERE src_id = %(id)s OR dst_id = %(id)s",
        {"id": lexeme_id},
    )
    cursor.execute("DELETE FROM lexeme WHERE id = %s", (lexeme_id,))


def backfill(database_url: str, *, execute: bool) -> Stats:
    """Delete every "-" placeholder lexeme found on `database_url`.

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
        placeholders = _find_dash_placeholder_lexemes(cursor)
        _log.info('found %d "-" lexeme(s)', len(placeholders))

        deleted = 0
        unsafe = 0
        for lexeme_id, lang_code in placeholders:
            if _sense_count(cursor, lexeme_id) > 0:
                _log.warning(
                    'unsafe: %s "-" carries its own senses, skipping',
                    lang_code,
                )
                unsafe += 1
                continue
            _log.info('delete: %s "-"', lang_code)
            _delete_dash_placeholder(cursor, lexeme_id)
            deleted += 1

        if execute:
            connection.commit()
        else:
            connection.rollback()

    stats = Stats(deleted=deleted, unsafe=unsafe)
    _log.info(
        "%s: deleted=%d unsafe=%d",
        "applied" if execute else "dry run (rolled back)",
        stats.deleted,
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
