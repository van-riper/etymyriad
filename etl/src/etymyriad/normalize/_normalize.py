"""The public per-entry-stream facade over the edge and lexeme builders."""

from __future__ import annotations

import dataclasses
import logging
import pickle
import tempfile
from typing import TYPE_CHECKING

from pydantic import ValidationError

from etymyriad.model import RelType
from etymyriad.normalize._edges import (
    _edges_from_entry,
    _is_entirely_form_of_entry,
)
from etymyriad.normalize._lexemes import lexeme_of_entry

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import EtymEdge, Lexeme

_log = logging.getLogger(__name__)

type _NaturalKey = tuple[str, str, str | None]


def _split_pos_identity(lexeme: Lexeme) -> Lexeme:
    """Give a lexeme its own natural key, distinguished by its own pos.

    Encodes the split into `etymology_number` (rather than a new key
    column) so the existing `etym_key`/unique-index machinery does the
    splitting with no schema change: two lexemes sharing a headword
    that differ only in this synthetic suffix land as two DB rows.

    Args:
        lexeme: An entirely-form-of dst sharing a homograph's key.

    Returns:
        `lexeme` with a synthetic `etymology_number` embedding its pos.
    """
    pos = lexeme.senses[0].pos if lexeme.senses else None
    suffix = f"formof:{pos or ''}"
    number = (
        f"{lexeme.etymology_number}#{suffix}"
        if lexeme.etymology_number
        else suffix
    )
    return dataclasses.replace(lexeme, etymology_number=number)


class _FormOfLexemeSpool:
    """Buffers an entirely-form-of entry's own dst for a deferred replay.

    Whether this dst shares a homograph lemma's key can only be known
    after the whole entry stream has been seen, so it can't be yielded
    (or split) at the point its own entry is processed.
    """

    def __init__(self) -> None:
        self._file = tempfile.TemporaryFile()
        self._size = 0

    def add(self, lexeme: Lexeme) -> None:
        """Buffer one entirely-form-of entry's own dst for later replay.

        Args:
            lexeme: The entry's own lexeme, not yet known to need
                splitting.
        """
        pickle.dump(lexeme, self._file)
        self._size += 1

    def replay(self, non_form_of_keys: set[_NaturalKey]) -> Iterator[Lexeme]:
        """Yield every buffered lexeme, split where a homograph exists.

        Args:
            non_form_of_keys: Every natural key seen on a NOT-entirely-
                form-of entry anywhere in the stream.

        Yields:
            Each buffered lexeme, split via `_split_pos_identity` when
            its key also belongs to a non-form-of sibling.
        """
        self._file.seek(0)
        for _ in range(self._size):
            lexeme = pickle.load(self._file)
            if lexeme.natural_key in non_form_of_keys:
                lexeme = _split_pos_identity(lexeme)
            yield lexeme
        self._file.close()


class _InflectionSpool:
    """Buffers inflection candidates for a filtered replay at stream end.

    A candidate's form can only be known to be cited after the whole
    entry stream has been seen, so candidates are held on disk rather
    than in memory -- up to ~5M can exist dump-wide, most never cited.
    Each candidate is tagged with whether its own entry was entirely
    form-of, since only that dst is ever eligible for the homograph
    split -- a mixed entry's own inflection edge must never split from
    its own natural key.
    """

    def __init__(self) -> None:
        self._file = tempfile.TemporaryFile()
        self._size = 0

    def add(self, candidate: EtymEdge, *, is_form_of_only: bool) -> None:
        """Buffer one candidate for later replay.

        Args:
            candidate: An inflection edge not yet known to be cited.
            is_form_of_only: Whether `candidate`'s own entry was
                entirely form-of.
        """
        pickle.dump((is_form_of_only, candidate), self._file)
        self._size += 1

    def replay(
        self, cited: set[_NaturalKey], non_form_of_keys: set[_NaturalKey]
    ) -> Iterator[EtymEdge]:
        """Yield every buffered candidate whose form is in `cited`.

        Args:
            cited: Every ancestor natural key seen among the stream's
                structural edges.
            non_form_of_keys: Every natural key seen on a NOT-entirely-
                form-of entry anywhere in the stream.

        Yields:
            Each candidate cited as an ancestor elsewhere in the stream,
            its dst split via `_split_pos_identity` when the candidate's
            own entry was entirely form-of and its dst's key also
            belongs to a non-form-of sibling.
        """
        self._file.seek(0)
        for _ in range(self._size):
            is_form_of_only, candidate = pickle.load(self._file)
            if candidate.dst.natural_key not in cited:
                continue
            if (
                is_form_of_only
                and candidate.dst.natural_key in non_form_of_keys
            ):
                candidate = dataclasses.replace(
                    candidate, dst=_split_pos_identity(candidate.dst)
                )
            yield candidate
        self._file.close()


def _edges_or_none(
    entry: Mapping[str, object], dump_date: str
) -> list[EtymEdge] | None:
    """Parse one entry's edges, or None if the entry is malformed.

    Args:
        entry: A raw Wiktextract entry.
        dump_date: The dump date pinned into each edge's provenance.

    Returns:
        The entry's edges, or None if `entry` failed validation.
    """
    try:
        return list(_edges_from_entry(entry, dump_date))
    except ValidationError as e:
        _log.warning("skipping malformed entry: %s", e)
        return None


def normalize(
    entries: Iterable[Mapping[str, object]],
    dump_date: str,
) -> Iterator[EtymEdge | Lexeme]:
    """Yield etymology edges for every entry in the stream.

    An entry with no recognized-ancestor template (e.g. clipping,
    unk/unc, cog/ncog/noncog, onom*) yields no edges from
    `_edges_from_entry`; its own lexeme+senses would otherwise never
    reach the load step, since the loader derives every row it upserts
    from edge endpoints. Falling back to the entry's own lexeme in that
    case is what keeps such an entry from silently vanishing.

    An inflection edge (a non-lemma form's sense pointing at its lemma
    via `form_of`) is emitted only when the form is cited as an
    ancestor somewhere else in the stream -- emitting one for every
    form-of sense unconditionally would nearly triple the edge table
    for forms nothing ever descends from. Since that can only be known
    after the whole stream has been seen, inflection candidates are
    spooled to a temp file while every other edge's ancestor natural
    key is collected, then replayed and filtered once the stream ends.

    A malformed entry (missing lang_code or word) is logged and skipped
    rather than aborting the rest of a run that can take over an hour
    against the full dump -- the same tradeoff `parse.stream_entries`
    makes for a malformed JSONL line.

    An entirely-form-of entry's own dst (e.g. la "aquila" the adjective,
    "ablative of aquilus") only splits away from a homograph lemma
    sharing its natural key (la "aquila" the noun, "eagle") when that
    homograph exists somewhere in the stream -- otherwise it merges
    exactly as before. Since a sibling can appear anywhere in the
    stream, this dst is deferred (like an inflection candidate) rather
    than yielded immediately.

    Args:
        entries: Parsed Wiktextract entries.
        dump_date: The dump date pinned into each edge's provenance.

    Yields:
        The etymology edges the stream produces (including a cited
        form's inflection edge, deferred to the end), and each entry's
        own lexeme when it produced no structural edge.
    """
    cited_ancestors: set[_NaturalKey] = set()
    non_form_of_keys: set[_NaturalKey] = set()
    lexeme_spool = _FormOfLexemeSpool()
    inflection_spool = _InflectionSpool()

    for entry in entries:
        edges = _edges_or_none(entry, dump_date)
        if edges is None:
            continue

        structural = [
            edge for edge in edges if edge.rel_type is not RelType.INFLECTION
        ]
        cited_ancestors.update(edge.src.natural_key for edge in structural)

        if structural:
            yield from structural
            non_form_of_keys.add(structural[0].dst.natural_key)
            is_form_of_only = False
        elif _is_entirely_form_of_entry(entry):
            lexeme_spool.add(lexeme_of_entry(entry, dump_date))
            is_form_of_only = True
        else:
            own = lexeme_of_entry(entry, dump_date)
            yield own
            non_form_of_keys.add(own.natural_key)
            is_form_of_only = False

        for candidate in edges:
            if candidate.rel_type is RelType.INFLECTION:
                inflection_spool.add(candidate, is_form_of_only=is_form_of_only)

    yield from lexeme_spool.replay(non_form_of_keys)
    yield from inflection_spool.replay(cited_ancestors, non_form_of_keys)
