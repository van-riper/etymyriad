"""The public per-entry-stream facade over the edge and term builders."""

from __future__ import annotations

import logging
import pickle
import tempfile
from typing import TYPE_CHECKING

from pydantic import ValidationError

from etymyriad.model import RelType
from etymyriad.normalize._edges import _edges_from_entry
from etymyriad.normalize._nodes import term_of_entry

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import EtymEdge, Term

_log = logging.getLogger(__name__)

type _TermKey = tuple[str, str]


class _InflectionSpool:
    """Buffers inflection candidates for a filtered replay at stream end.

    A candidate's form can only be known to be cited after the whole
    entry stream has been seen, so candidates are held on disk rather
    than in memory (up to ~5M can exist dump-wide, most never cited).
    """

    def __init__(self) -> None:
        self._file = tempfile.TemporaryFile()
        self._size = 0

    def add(self, candidate: EtymEdge) -> None:
        """Buffer one candidate for later replay.

        Args:
            candidate: An inflection edge not yet known to be cited.
        """
        pickle.dump(candidate, self._file)
        self._size += 1

    def replay(self, cited: set[_TermKey]) -> Iterator[EtymEdge]:
        """Yield every buffered candidate whose form is in `cited`.

        Args:
            cited: Every ancestor term key seen among the stream's
                structural edges.

        Yields:
            Each candidate cited as an ancestor elsewhere in the stream.
        """
        self._file.seek(0)
        for _ in range(self._size):
            candidate = pickle.load(self._file)
            if candidate.dst.key in cited:
                yield candidate
        self._file.close()


def _edges_or_none(entry: Mapping[str, object]) -> list[EtymEdge] | None:
    """Parse one entry's edges, or None if the entry is malformed.

    Args:
        entry: A raw Wiktextract entry.

    Returns:
        The entry's edges, or None if `entry` failed validation.
    """
    try:
        return list(_edges_from_entry(entry))
    except ValidationError as e:
        _log.warning("skipping malformed entry: %s", e)
        return None


def normalize(
    entries: Iterable[Mapping[str, object]],
) -> Iterator[EtymEdge | Term]:
    """Yield etymology edges and terms for every entry in the stream.

    An entry with no recognized-ancestor template (e.g. clipping,
    unk/unc, cog/ncog/noncog, onom*) yields no edges from
    `_edges_from_entry`; its own term and senses would otherwise never
    reach the load step, since the loader derives every row it upserts
    from edge endpoints. Falling back to the entry's own term in that
    case is what keeps such an entry from silently vanishing.

    An inflection edge (a non-lemma form's sense pointing at its lemma
    via `form_of`) is emitted only when the form is cited as an
    ancestor somewhere else in the stream. Emitting one for every
    form-of sense unconditionally would nearly triple the edge table
    for forms nothing ever descends from. Since that can only be known
    after the whole stream has been seen, inflection candidates are
    spooled to a temp file while every other edge's ancestor key is
    collected, then replayed and filtered once the stream ends.

    A malformed entry (missing lang_code or word) is logged and skipped
    rather than aborting the rest of a run that can take over an hour
    against the full dump, the same tradeoff `parse.stream_entries`
    makes for a malformed JSONL line.

    Args:
        entries: Parsed Wiktextract entries.

    Yields:
        The etymology edges the stream produces (including a cited
        form's inflection edge, deferred to the end), and each entry's
        own term when it produced no structural edge.
    """
    cited_ancestors: set[_TermKey] = set()
    inflection_spool = _InflectionSpool()

    for entry in entries:
        edges = _edges_or_none(entry)
        if edges is None:
            continue

        structural = [
            edge for edge in edges if edge.rel_type is not RelType.INFLECTION
        ]
        cited_ancestors.update(edge.src.key for edge in structural)
        if structural:
            yield from structural
        else:
            yield term_of_entry(entry)

        for candidate in edges:
            if candidate.rel_type is RelType.INFLECTION:
                inflection_spool.add(candidate)

    yield from inflection_spool.replay(cited_ancestors)
