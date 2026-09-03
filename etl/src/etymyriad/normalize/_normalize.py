"""The public per-entry-stream facade over the edge and lexeme builders."""

from __future__ import annotations

import logging
import pickle
import tempfile
from typing import TYPE_CHECKING

from pydantic import ValidationError

from etymyriad.model import RelType
from etymyriad.normalize._edges import _edges_from_entry
from etymyriad.normalize._lexemes import lexeme_of_entry

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import EtymEdge, Lexeme

_log = logging.getLogger(__name__)

type _NaturalKey = tuple[str, str, str | None]


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

    Args:
        entries: Parsed Wiktextract entries.
        dump_date: The dump date pinned into each edge's provenance.

    Yields:
        The etymology edges the stream produces (including a cited
        form's inflection edge, deferred to the end), and each entry's
        own lexeme when it produced no structural edge.
    """
    cited_ancestors: set[_NaturalKey] = set()
    spool_size = 0
    with tempfile.TemporaryFile() as spool:
        for entry in entries:
            try:
                edges = list(_edges_from_entry(entry, dump_date))
            except ValidationError as e:
                _log.warning("skipping malformed entry: %s", e)
                continue

            structural = [
                edge
                for edge in edges
                if edge.rel_type is not RelType.INFLECTION
            ]
            cited_ancestors.update(edge.src.natural_key for edge in structural)
            if structural:
                yield from structural
            else:
                yield lexeme_of_entry(entry, dump_date)

            for candidate in edges:
                if candidate.rel_type is RelType.INFLECTION:
                    pickle.dump(candidate, spool)
                    spool_size += 1

        spool.seek(0)
        for _ in range(spool_size):
            candidate = pickle.load(spool)
            if candidate.dst.natural_key in cited_ancestors:
                yield candidate
