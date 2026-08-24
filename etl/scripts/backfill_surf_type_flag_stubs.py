#!/usr/bin/env python3
"""Reconcile {{surf}} edges against the fixed parser's ground truth.

`normalize.py`'s affix-family parsing now reads {{surf}}'s optional
leading "+type" flag (e.g. "+suf", "+deverbal") as the annotation it
is, instead of mistaking it for the ancestor pieces' language, and
correctly counts pieces starting after it. That fix only applies to
future loads.

Every row loaded before it is wrong in one of two ways. Most generic
flags leaked the citing entry's own language argument in as a phantom
extra piece (e.g. {{surf|+clipping|pl|kilogram}} produced a bogus "pl"
piece alongside the real "kilogram" one), since the old piece-counting
never skipped past the language argument the flag's presence implies.
And every piece, phantom or real, was keyed on the flag string itself
as its bogus "language" instead of the real one.

Reconciling this from lexeme/edge identity alone cannot tell a real
mislabeled piece from a phantom leaked-language one; both look like
"some node cited once from a known language". Instead, this rebuilds
the correct edge set directly from the raw dump with the fixed parser,
keyed by each surf template's own source_ref (stable across every
mutation this script or its predecessor made), and reconciles the
database against that ground truth per source_ref: a current edge
matching a correct piece by headword is repointed onto the real
language and given the right piece_order; one matching no correct
piece at all is a phantom and is deleted; any correct piece missing
a current edge is inserted, finding or creating its target lexeme.
Afterward, any lexeme this run touched that ends up with no senses and
no remaining edges anywhere is deleted as an orphaned stub.

Known limitation: reconciliation assumes each source_ref's pieces have
distinct headwords, matching a current edge to the correct piece by
headword text. A template with two identical-text pieces (e.g. a
reduplication) cannot be told apart this way; confirmed absent from
every {{surf}} occurrence in the local full load, so this is a
theoretical gap, not an observed one. This also assumes the dump at
`WIKTEXTRACT_DUMP` is the same one the affected rows were loaded from;
a source_ref with no matching dump entry is reported as unresolved
rather than guessed at.

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
import operator
from collections import defaultdict
from dataclasses import dataclass
from itertools import groupby
from typing import TYPE_CHECKING

import psycopg

from etymyriad.config import Config
from etymyriad.model import RelType
from etymyriad.normalize import normalize
from etymyriad.parse import stream_entries

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
_log = logging.getLogger(__name__)

# One correct piece: (lang_code, headword, piece_order).
_CorrectPiece = tuple[str, str, int]

# One current row from the database: (edge id, piece_order, src id,
# src lang_code, src headword, dst id), all but piece_order as text.
_CurrentRow = tuple[str, int | None, str, str, str, str]


@dataclass(frozen=True, slots=True)
class Stats:
    """Outcome tally for one backfill run.

    Attributes:
        repaired: Edges repointed onto the real language and/or given
            the correct piece_order.
        deleted: Phantom edges deleted, matching no correct piece.
        inserted: Correct pieces missing an edge entirely, inserted.
        unresolved: source_refs with no matching dump entry, left
            untouched.
        orphans_deleted: Stub lexemes left with no senses and no edges
            after reconciliation, deleted.
    """

    repaired: int = 0
    deleted: int = 0
    inserted: int = 0
    unresolved: int = 0
    orphans_deleted: int = 0


def _correct_pieces(
    entries: Iterable[Mapping[str, object]], dump_date: str
) -> dict[str, list[_CorrectPiece]]:
    """Rebuild every {{surf}} template's correct pieces from the dump.

    Args:
        entries: Parsed Wiktextract entries.
        dump_date: The dump date pinned into each entry's source_ref.

    Returns:
        Every surf template's source_ref mapped to its correct
        (lang_code, headword, piece_order) pieces, in the fixed
        parser's own order.
    """
    correct: dict[str, list[_CorrectPiece]] = defaultdict(list)
    for edge in normalize(entries, dump_date):
        if (
            edge.rel_type is RelType.SURFACE_ANALYSIS
            and edge.piece_order is not None
        ):
            correct[edge.source_ref].append((
                edge.src.lang_code,
                edge.src.headword,
                edge.piece_order,
            ))
    return correct


def _current_rows(cursor: psycopg.Cursor) -> dict[str, list[_CurrentRow]]:
    """Return every current surface_analysis edge, grouped by source_ref.

    Returns:
        Each source_ref mapped to its (edge id, piece_order, src id,
        src lang_code, src headword, dst id) rows. Every source_ref's
        rows share one dst id, the entry that cites this template.
    """
    cursor.execute(
        "SELECT e.source_ref, e.id::text, e.piece_order, e.src_id::text, "
        "src.lang_code, src.headword, e.dst_id::text FROM etymology e "
        "JOIN lexeme src ON src.id = e.src_id "
        "WHERE e.rel_type = 'surface_analysis' ORDER BY e.source_ref"
    )
    return {
        source_ref: [row[1:] for row in rows]
        for source_ref, rows in groupby(
            cursor.fetchall(), key=operator.itemgetter(0)
        )
    }


def _find_or_create_lexeme(
    cursor: psycopg.Cursor, lang_code: str, headword: str, source_ref: str
) -> str:
    """Find a real lexeme for (lang_code, headword), or stub one in.

    A new stub mirrors `_referenced_lexeme` in normalize.py: no
    etymology_number, no senses, is_redlink true. `source_ref` is
    rebuilt from the group's own dump date, matching the real
    provenance of the piece it corrects.

    Returns:
        The matching or newly created lexeme's id, as text.

    Raises:
        RuntimeError: If the insert unexpectedly returns no row.
    """
    cursor.execute(
        "SELECT id::text FROM lexeme WHERE lang_code = %s AND headword = %s "
        "AND etymology_number IS NULL",
        (lang_code, headword),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    _, dump_date, _, _ = source_ref.split(":", 3)
    cursor.execute(
        "INSERT INTO lexeme (lang_code, headword, is_redlink, source_ref) "
        "VALUES (%s, %s, true, %s) RETURNING id::text",
        (lang_code, headword, f"wiktionary:{dump_date}:{lang_code}:{headword}"),
    )
    row = cursor.fetchone()
    if row is None:
        msg = f"insert of lexeme {lang_code}/{headword} returned no row"
        raise RuntimeError(msg)
    return row[0]


def _upsert_edge(
    cursor: psycopg.Cursor,
    target_id: str,
    dst_id: str,
    source_ref: str,
    piece_order: int,
) -> None:
    """Insert a correct edge, fixing piece_order if one already exists.

    Under etymology_unique_edge, an edge already at (target_id, dst_id)
    gets its piece_order corrected in place instead of colliding.
    """
    cursor.execute(
        """
        INSERT INTO etymology
            (src_id, dst_id, rel_type, source_ref, piece_order)
        VALUES (%s, %s, 'surface_analysis', %s, %s)
        ON CONFLICT (src_id, dst_id, rel_type)
        DO UPDATE SET piece_order = EXCLUDED.piece_order
        """,
        (target_id, dst_id, source_ref, piece_order),
    )


def _reconcile_group(
    cursor: psycopg.Cursor,
    source_ref: str,
    current: list[_CurrentRow],
    correct: list[_CorrectPiece],
    touched_lexeme_ids: set[str],
) -> tuple[int, int, int]:
    """Reconcile one source_ref's current edges against its correct pieces.

    Returns:
        (repaired, deleted, inserted) counts for this group.
    """
    correct_by_headword = {
        headword: (lang_code, piece_order)
        for lang_code, headword, piece_order in correct
    }
    dst_id = current[0][-1]
    seen_headwords: set[str] = set()
    repaired = deleted = 0

    for edge_id, piece_order, src_id, src_lang, src_headword, _ in current:
        match = correct_by_headword.get(src_headword)
        if match is None:
            _log.info("delete phantom: %s/%s", src_lang, src_headword)
            cursor.execute("DELETE FROM etymology WHERE id = %s", (edge_id,))
            touched_lexeme_ids.add(src_id)
            deleted += 1
            continue

        seen_headwords.add(src_headword)
        correct_lang, correct_piece_order = match
        if src_lang == correct_lang and piece_order == correct_piece_order:
            continue

        if src_lang == correct_lang:
            _log.info(
                "repair piece_order: %s/%s -> piece %d",
                src_lang,
                src_headword,
                correct_piece_order,
            )
            cursor.execute(
                "UPDATE etymology SET piece_order = %s WHERE id = %s",
                (correct_piece_order, edge_id),
            )
        else:
            _log.info(
                "repoint: %s/%s -> %s/%s (piece %d)",
                src_lang,
                src_headword,
                correct_lang,
                src_headword,
                correct_piece_order,
            )
            target_id = _find_or_create_lexeme(
                cursor, correct_lang, src_headword, source_ref
            )
            _upsert_edge(
                cursor, target_id, dst_id, source_ref, correct_piece_order
            )
            cursor.execute("DELETE FROM etymology WHERE id = %s", (edge_id,))
            touched_lexeme_ids.add(src_id)
        repaired += 1

    inserted = 0
    for lang_code, headword, piece_order in correct:
        if headword in seen_headwords:
            continue
        _log.info("insert missing: %s/%s", lang_code, headword)
        target_id = _find_or_create_lexeme(
            cursor, lang_code, headword, source_ref
        )
        _upsert_edge(cursor, target_id, dst_id, source_ref, piece_order)
        inserted += 1

    return repaired, deleted, inserted


def _delete_orphans(cursor: psycopg.Cursor, lexeme_ids: set[str]) -> int:
    """Delete any of `lexeme_ids` left with no senses and no edges.

    Returns:
        How many were deleted.
    """
    if not lexeme_ids:
        return 0
    cursor.execute(
        """
        DELETE FROM lexeme
        WHERE id = ANY(%(ids)s)
          AND NOT EXISTS (SELECT 1 FROM sense WHERE lexeme_id = lexeme.id)
          AND NOT EXISTS (
              SELECT 1 FROM etymology
              WHERE src_id = lexeme.id OR dst_id = lexeme.id
          )
        """,
        {"ids": list(lexeme_ids)},
    )
    return cursor.rowcount


def backfill(
    database_url: str,
    entries: Iterable[Mapping[str, object]],
    dump_date: str,
    *,
    execute: bool,
) -> Stats:
    """Reconcile every surface_analysis edge on `database_url`.

    Args:
        database_url: Postgres connection string.
        entries: Parsed Wiktextract entries, the ground truth every
            surface_analysis edge is checked against.
        dump_date: The dump date pinned into any newly created lexeme.
        execute: Commit the transaction if True; roll it back (dry
            run) if False.

    Returns:
        The run's outcome tally.
    """
    correct_pieces = _correct_pieces(entries, dump_date)

    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        current = _current_rows(cursor)
        _log.info(
            "found %d surf template group(s) in the database", len(current)
        )

        repaired = deleted = inserted = unresolved = 0
        touched_lexeme_ids: set[str] = set()
        for source_ref, rows in current.items():
            correct = correct_pieces.get(source_ref)
            if correct is None:
                _log.warning("unresolved: %s not found in dump", source_ref)
                unresolved += 1
                continue
            group_repaired, group_deleted, group_inserted = _reconcile_group(
                cursor, source_ref, rows, correct, touched_lexeme_ids
            )
            repaired += group_repaired
            deleted += group_deleted
            inserted += group_inserted

        orphans_deleted = _delete_orphans(cursor, touched_lexeme_ids)

        if execute:
            connection.commit()
        else:
            connection.rollback()

    stats = Stats(
        repaired=repaired,
        deleted=deleted,
        inserted=inserted,
        unresolved=unresolved,
        orphans_deleted=orphans_deleted,
    )
    _log.info(
        "%s: repaired=%d deleted=%d inserted=%d unresolved=%d "
        "orphans_deleted=%d",
        "applied" if execute else "dry run (rolled back)",
        stats.repaired,
        stats.deleted,
        stats.inserted,
        stats.unresolved,
        stats.orphans_deleted,
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
    backfill(
        config.database_url,
        stream_entries(config.dump_path),
        config.dump_date,
        execute=args.execute,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
