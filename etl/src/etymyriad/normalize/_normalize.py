"""The public per-entry-stream facade over the edge and lexeme builders."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from etymyriad.normalize._edges import _edges_from_entry
from etymyriad.normalize._lexemes import lexeme_of_entry

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import EtymEdge, Lexeme

_log = logging.getLogger(__name__)


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

    A malformed entry (missing lang_code or word) is logged and skipped
    rather than aborting the rest of a run that can take over an hour
    against the full dump -- the same tradeoff `parse.stream_entries`
    makes for a malformed JSONL line.

    Args:
        entries: Parsed Wiktextract entries.
        dump_date: The dump date pinned into each edge's provenance.

    Yields:
        The etymology edges the stream produces, and each entry's own
        lexeme when it produced none.
    """
    for entry in entries:
        try:
            edges = list(_edges_from_entry(entry, dump_date))
        except ValidationError as e:
            _log.warning("skipping malformed entry: %s", e)
            continue
        if edges:
            yield from edges
        else:
            yield lexeme_of_entry(entry, dump_date)
