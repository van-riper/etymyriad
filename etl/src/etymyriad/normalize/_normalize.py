"""The public per-entry-stream facade over the edge and term builders."""

import logging
import pickle
import tempfile
import unicodedata
from collections import Counter
from dataclasses import replace
from typing import TYPE_CHECKING

from etymyriad.config import UNMAPPED_LOG_LIMIT
from etymyriad.languages import resolve_language
from etymyriad.model import RelType
from etymyriad.normalize._edges import (
    _edges_from_entry,
    _unmapped_relation_names,
)
from etymyriad.normalize._nodes import term_of_entry
from etymyriad.normalize._sections import section_claims

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from etymyriad.model import EtymEdge, GraphItem, Term
    from etymyriad.normalize._wiktextract import WiktextractEntry

_log = logging.getLogger(__name__)

type _TermKey = tuple[str, str]

# Macron and breve, the marks the loader's stub alias also strips.
_LENGTH_MARKS = str.maketrans("", "", "\u0304\u0306")


def _length_folded(key: _TermKey) -> _TermKey:
    """Drop vowel-length marks from a key's headword.

    A form_of target often spells its lemma with macrons or breves the
    lemma's page title omits (la "signō" for "signo").

    Args:
        key: A term key.

    Returns:
        The key with its headword decomposed and its length marks gone.
    """
    lang_code, headword = key
    decomposed = unicodedata.normalize("NFD", headword)
    return lang_code, decomposed.translate(_LENGTH_MARKS)


def _lemma_page(lemma: Term, pages: set[_TermKey]) -> Term | None:
    """Find the spelling under which a form_of lemma has a page.

    A lemma cited with stress marks (bg "пека́") is titled without them
    ("пека"), by its language's rule. The spelling as cited wins when
    it has a page of its own, since the rule can turn one word into
    another (nn "allé" into "alle").

    Args:
        lemma: The lemma a form_of sense names.
        pages: Every entry's own term key in the stream,
            length-folded.

    Returns:
        The lemma as cited, or as its page titles spell it, whichever
        has a page first; None when neither has one.
    """
    if _length_folded(lemma.key) in pages:
        return lemma
    language = resolve_language(lemma.lang_code)
    if language is None:
        return None
    titled = replace(lemma, headword=language.strip_diacritics(lemma.headword))
    return titled if _length_folded(titled.key) in pages else None


class _InflectionSpool:
    """Buffers inflection candidates for a filtered replay at stream end.

    Whether a candidate's lemma has a page can only be known after the
    whole entry stream has been seen, so candidates are held on disk
    rather than in memory (about 5M exist dump-wide).
    """

    def __init__(self) -> None:
        self._file = tempfile.TemporaryFile()
        self._size = 0

    def add(self, candidate: EtymEdge) -> None:
        """Buffer one candidate for later replay.

        Args:
            candidate: An inflection edge whose lemma is not yet known
                to have a page.
        """
        pickle.dump(candidate, self._file)
        self._size += 1

    def replay(self, pages: set[_TermKey]) -> Iterator[EtymEdge]:
        """Yield every buffered candidate whose lemma is in `pages`.

        Args:
            pages: Every entry's own term key in the stream,
                length-folded.

        Yields:
            Each candidate whose lemma has a page of its own, its src
            spelled the way that page is found.
        """
        self._file.seek(0)
        for _ in range(self._size):
            candidate = pickle.load(self._file)
            if (lemma := _lemma_page(candidate.src, pages)) is not None:
                yield replace(candidate, src=lemma)
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
    via `form_of`) is emitted only when the lemma has a page of its
    own, so a form_of target with no entry never becomes an empty
    node. Keys are compared without vowel-length marks, the same fold
    the loader's stub alias applies, and a lemma with no page as cited
    is looked up again as its language titles pages (without stress
    marks, for ru, uk, and bg). Since that can only be known
    after the whole stream has been seen, inflection candidates are
    spooled to a temp file while every entry's key is collected, then
    replayed and filtered once the stream ends.

    A numbered section's claims (the ids it declares, the terms it
    lists) follow its entry's edges, so the loader can tell which
    section of a page an edge into it means.

    An edge whose ends share a (language, headword) key is dropped:
    tree nodes are terms, so it would make a node its own parent. That
    loses real ancestry where an etymology-only variety files under its
    full language (lmo "de" from Old Lombard "de") or a template points
    at another section of the same word. Drops are counted by kind and
    logged once the stream ends.

    Every template name and {{etymon}} code that is neither mapped nor
    deliberately ignored is counted and logged once the stream ends, so
    a relation Wiktionary starts using shows up instead of vanishing.

    Args:
        entries: Decoded Wiktextract entries.

    Yields:
        The etymology edges the stream produces (including each
        inflection edge whose lemma has a page, deferred to the end),
        each entry's own term when it produced no structural edge, and
        each numbered section's claims.
    """
    pages: set[_TermKey] = set()
    inflection_spool = _InflectionSpool()
    unmapped: Counter[str] = Counter()
    self_loops: Counter[str] = Counter()

    for entry in entries:
        pages.add(_length_folded(term_of_entry(entry).key))
        edges: list[EtymEdge] = []
        for edge in _edges_from_entry(entry):
            if edge.src.key == edge.dst.key:
                self_loops[_self_loop_kind(edge)] += 1
            else:
                edges.append(edge)
        unmapped.update(_unmapped_relation_names(entry))

        structural = [
            edge for edge in edges if edge.rel_type is not RelType.INFLECTION
        ]
        if structural:
            yield from structural
        else:
            yield term_of_entry(entry)
        yield from section_claims(entry)

        for candidate in edges:
            if candidate.rel_type is RelType.INFLECTION:
                inflection_spool.add(candidate)

    yield from inflection_spool.replay(pages)
    _log_unmapped(unmapped)
    _log_self_loops(self_loops)


def _self_loop_kind(edge: EtymEdge) -> str:
    """Name what an edge from a term to itself connects.

    Args:
        edge: An edge whose src and dst share a node key.

    Returns:
        "inflection" for a form-of sense naming its own headword, else
        "variety" when the ends name different varieties, else
        "section" when they name different sections, else "same term".
    """
    if edge.rel_type is RelType.INFLECTION:
        return "inflection"
    if edge.src.variety_code != edge.dst.variety_code:
        return "variety"
    if edge.src.section != edge.dst.section:
        return "section"
    return "same term"


def _log_self_loops(self_loops: Counter[str]) -> None:
    """Log how many edges from a term to itself were dropped, by kind.

    Args:
        self_loops: Dropped edges per `_self_loop_kind`.
    """
    if not self_loops:
        return
    summary = ", ".join(
        f"{kind} ({count:,})" for kind, count in self_loops.most_common()
    )
    _log.info(
        "dropped self-loop edges (%s): %s",
        f"{self_loops.total():,}",
        summary,
    )


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
