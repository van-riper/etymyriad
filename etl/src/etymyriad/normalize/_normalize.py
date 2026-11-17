"""The public per-entry-stream facade over the edge and term builders."""

from __future__ import annotations

import logging
import pickle
import tempfile
from collections import Counter
from typing import TYPE_CHECKING

from etymyriad.config import UNMAPPED_LOG_LIMIT
from etymyriad.model import RelType
from etymyriad.normalize._edges import (
    _edges_from_entry,
    _unmapped_relation_names,
)
from etymyriad.normalize._nodes import term_of_entry
from etymyriad.normalize._sections import section_claims

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from etymyriad.model import EtymEdge, GraphItem
    from etymyriad.normalize._wiktextract import WiktextractEntry

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


def normalize(
    entries: Iterable[WiktextractEntry],
) -> Iterator[GraphItem]:
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

    A numbered section's claims (the ids it declares, the terms it
    lists) follow its entry's edges, so the loader can tell which
    section of a page an edge into it means.

    Every template name and {{etymon}} code that is neither mapped nor
    deliberately ignored is counted and logged once the stream ends, so
    a relation Wiktionary starts using shows up instead of vanishing.

    Args:
        entries: Decoded Wiktextract entries.

    Yields:
        The etymology edges the stream produces (including a cited
        form's inflection edge, deferred to the end), and each entry's
        own term when it produced no structural edge, and each
        numbered section's claims.
    """
    cited_ancestors: set[_TermKey] = set()
    inflection_spool = _InflectionSpool()
    unmapped: Counter[str] = Counter()

    for entry in entries:
        edges = list(_edges_from_entry(entry))
        unmapped.update(_unmapped_relation_names(entry))

        structural = [
            edge for edge in edges if edge.rel_type is not RelType.INFLECTION
        ]
        cited_ancestors.update(edge.src.key for edge in structural)
        if structural:
            yield from structural
        else:
            yield term_of_entry(entry)
        yield from section_claims(entry)

        for candidate in edges:
            if candidate.rel_type is RelType.INFLECTION:
                inflection_spool.add(candidate)

    yield from inflection_spool.replay(cited_ancestors)
    _log_unmapped(unmapped)


def _log_unmapped(unmapped: Counter[str]) -> None:
    """Log the most-used template names and codes nothing classifies.

    Args:
        unmapped: Uses per unmapped, unignored template name or code.
    """
    if not unmapped:
        return
    top = unmapped.most_common(UNMAPPED_LOG_LIMIT)
    summary = ", ".join(f"{name} ({count:,})" for name, count in top)
    _log.info(
        "unmapped etymology templates and codes (%s kinds): %s",
        f"{len(unmapped):,}",
        summary,
    )
