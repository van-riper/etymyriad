#!/usr/bin/env python3
"""Merge inline-annotation-leaked lexeme nodes.

`_referenced_lexeme` now strips Wiktextract's trailing "<...>"
disambiguation annotation (e.g. "un-<id:reversive>") before parsing,
but rows already loaded onto Neon before that fix still carry
annotated terms as their own lexeme nodes instead of merging with the
real stripped headword (e.g. "un-").

This script finds every lexeme whose headword still contains "<", and
for the ones that match that exact leaked-annotation shape -- a bare
word followed by one "<tag>" or "<tag:value>" block and nothing else
-- works out the correct (unannotated) headword and either:

  * merges it into the existing real node for that (lang_code,
    headword) if one already exists -- repointing its edges, then
    deleting the annotated duplicate; or
  * renames it in place if no real node exists yet.

A live dry run turned up headwords containing "<" for an unrelated
reason: raw HTML mention markup (e.g. `<i class="Latn mention"
lang="cy">hon</i> ("this")`) or a newline-joined pair of entries
leaked in from a different bug entirely, where naively splitting on
the first "<" would rename the row to an empty or still-garbled
headword. Those, along with ambiguous cases (more than one real-node
candidate, since etym_key disambiguates by etymology_number and a
leaked node carries none) and unsafe cases (the leaked node picked up
its own sense rows, which a merge would silently drop), are left
untouched and reported, not guessed at.

Runs as a dry run by default: it always executes inside a transaction
and only commits with --execute; otherwise it prints the plan and
rolls back.

Usage:
  ./etl/scripts/backfill_annotation_leaks.py            # dry run
  ./etl/scripts/backfill_annotation_leaks.py --execute   # apply
"""

from __future__ import annotations

import argparse
import logging
import re
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
        merged: Leaked lexemes repointed onto an existing real node and
            deleted.
        renamed: Leaked lexemes renamed in place (no real node existed).
        ambiguous: Leaked lexemes left untouched, matching more than one
            real node.
        unsafe: Leaked lexemes left untouched, carrying their own sense
            rows a merge would have dropped.
        unrecognized: Leaked lexemes left untouched, since their headword
            doesn't match the known leaked-annotation shape.
    """

    merged: int = 0
    renamed: int = 0
    ambiguous: int = 0
    unsafe: int = 0
    unrecognized: int = 0


class _Outcome(StrEnum):
    """Which of the five ways one leaked lexeme was resolved."""

    MERGED = "merged"
    RENAMED = "renamed"
    AMBIGUOUS = "ambiguous"
    UNSAFE = "unsafe"
    UNRECOGNIZED = "unrecognized"


# A leaked annotation is a bare word followed by exactly one "<tag>" or
# "<tag:value>" block running to the end of the string. The tag itself
# must butt directly against "<" and either ">" or ":" -- never a
# space -- which is what an HTML mention tag like `<i class="Latn
# mention" ...>` never satisfies, so this never mistakes raw markup
# leaked in from an unrelated bug for a genuine annotation.
_LEAKED_ANNOTATION_RE = re.compile(
    r"^(?P<headword>[^<\n]+)<[a-z][a-z0-9_]*(:[^\n]*)?>$"
)


def _correct_headword(leaked_headword: str) -> str | None:
    """Extract the real headword from a leaked "<...>" annotation.

    Mirrors `_strip_inline_annotation` in normalize.py, applied after
    the fact to a headword that already went through `_strip_star`
    (the buggy path stripped the star but never the annotation).

    Returns:
        The real headword, or None if `leaked_headword` doesn't match
        the known leaked-annotation shape.
    """
    match = _LEAKED_ANNOTATION_RE.match(leaked_headword)
    return match["headword"] if match else None


def _find_leaked_lexemes(
    cursor: psycopg.Cursor,
) -> list[tuple[str, str, str]]:
    """Return every lexeme still carrying a leaked annotation.

    Returns:
        (id, lang_code, headword) rows, id as text.
    """
    cursor.execute(
        "SELECT id::text, lang_code, headword FROM lexeme "
        "WHERE headword LIKE '%<%' ORDER BY lang_code, headword"
    )
    return cursor.fetchall()


def _find_merge_target(
    cursor: psycopg.Cursor, lang_code: str, correct_headword: str
) -> list[str]:
    """Find real-node candidates for a leaked lexeme's correct headword.

    Returns:
        Matching lexeme ids (as text), 0, 1, or more.
    """
    cursor.execute(
        "SELECT id::text FROM lexeme WHERE lang_code = %s AND headword = %s",
        (lang_code, correct_headword),
    )
    return [row[0] for row in cursor.fetchall()]


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
    the caller afterward, cascading anything left.
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


def _resolve_leaked_lexeme(
    cursor: psycopg.Cursor, old_id: str, lang_code: str, headword: str
) -> _Outcome:
    """Merge, rename, or flag one leaked lexeme as unresolved.

    Args:
        cursor: An open cursor inside the run's transaction.
        old_id: The leaked lexeme's id.
        lang_code: The leaked lexeme's language code.
        headword: The leaked lexeme's stored (annotated) headword.

    Returns:
        Which of the five outcomes this lexeme resolved to.
    """
    correct_headword = _correct_headword(headword)
    if correct_headword is None:
        _log.warning(
            "unrecognized: %s/%s doesn't match the leaked-annotation "
            "shape, skipping",
            lang_code,
            headword,
        )
        return _Outcome.UNRECOGNIZED

    candidates = _find_merge_target(cursor, lang_code, correct_headword)

    if len(candidates) > 1:
        _log.warning(
            "ambiguous: %s/%s -> %r matches %d real nodes, skipping",
            lang_code,
            headword,
            correct_headword,
            len(candidates),
        )
        return _Outcome.AMBIGUOUS

    if not candidates:
        _log.info(
            "rename: %s/%s -> %s/%s",
            lang_code,
            headword,
            lang_code,
            correct_headword,
        )
        cursor.execute(
            "UPDATE lexeme SET headword = %s WHERE id = %s",
            (correct_headword, old_id),
        )
        return _Outcome.RENAMED

    target_id = candidates[0]
    if _sense_count(cursor, old_id) > 0:
        _log.warning(
            "unsafe: %s/%s carries its own senses, skipping",
            lang_code,
            headword,
        )
        return _Outcome.UNSAFE

    _log.info(
        "merge: %s/%s -> %s/%s",
        lang_code,
        headword,
        lang_code,
        correct_headword,
    )
    _repoint_edges(cursor, old_id, target_id)
    cursor.execute("DELETE FROM lexeme WHERE id = %s", (old_id,))
    return _Outcome.MERGED


def backfill(database_url: str, *, execute: bool) -> Stats:
    """Merge or rename every leaked lexeme found on `database_url`.

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
        leaked = _find_leaked_lexemes(cursor)
        _log.info("found %d leaked lexeme(s)", len(leaked))

        outcomes = Counter(
            _resolve_leaked_lexeme(cursor, old_id, lang_code, headword)
            for old_id, lang_code, headword in leaked
        )

        if execute:
            connection.commit()
        else:
            connection.rollback()

    stats = Stats(
        merged=outcomes[_Outcome.MERGED],
        renamed=outcomes[_Outcome.RENAMED],
        ambiguous=outcomes[_Outcome.AMBIGUOUS],
        unsafe=outcomes[_Outcome.UNSAFE],
        unrecognized=outcomes[_Outcome.UNRECOGNIZED],
    )
    _log.info(
        "%s: merged=%d renamed=%d ambiguous=%d unsafe=%d unrecognized=%d",
        "applied" if execute else "dry run (rolled back)",
        stats.merged,
        stats.renamed,
        stats.ambiguous,
        stats.unsafe,
        stats.unrecognized,
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
