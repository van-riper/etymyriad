"""The graph model. Mirrors `db/schema.sql` exactly.

A `Term` is a node. An `EtymEdge` is a directed ancestor -> descendant
relation. Both are frozen so they can be deduplicated in sets before loading.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple

# A Wiktionary language code suffix marking a reconstructed proto-language
# (e.g. "gem-pro" for Proto-Germanic).
PROTO_LANG_SUFFIX = "-pro"


class RelType(StrEnum):
    """Etymological relation types, matching the etym_rel_type SQL enum."""

    INHERITED = "inherited"
    BORROWED = "borrowed"
    LEARNED_BORROWING = "learned_borrowing"
    SEMI_LEARNED_BORROWING = "semi_learned_borrowing"
    DERIVED = "derived"
    ROOT = "root"
    AFFIX = "affix"
    COMPOUND = "compound"
    CALQUE = "calque"
    MENTION = "mention"
    SURFACE_ANALYSIS = "surface_analysis"
    INFLECTION = "inflection"


class RelTypeLabel(NamedTuple):
    """A relation type's display form, for the web app's edge labels.

    Attributes:
        abbreviation: Short form shown directly on an edge.
        full_name: Unabbreviated form, shown on hover/tap.
    """

    abbreviation: str
    full_name: str


# For display in the web app's edge labels. Kept here as the
# canonical source; mirrored by web/src/lib/shared/types.ts's
# REL_TYPE_LABELS.
REL_TYPE_LABELS: dict[RelType, RelTypeLabel] = {
    RelType.INHERITED: RelTypeLabel("inh.", "Inherited"),
    RelType.BORROWED: RelTypeLabel("bor.", "Borrowed"),
    RelType.LEARNED_BORROWING: RelTypeLabel("l.bor.", "Learned borrowing"),
    RelType.SEMI_LEARNED_BORROWING: RelTypeLabel(
        "s.l.bor.", "Semi-learned borrowing"
    ),
    RelType.DERIVED: RelTypeLabel("der.", "Derived"),
    RelType.ROOT: RelTypeLabel("root", "Root"),
    RelType.AFFIX: RelTypeLabel("affix", "Affix"),
    RelType.COMPOUND: RelTypeLabel("comp.", "Compound"),
    RelType.CALQUE: RelTypeLabel("calque", "Calque"),
    RelType.MENTION: RelTypeLabel("ment.", "Mention"),
    RelType.SURFACE_ANALYSIS: RelTypeLabel("s.a.", "Surface analysis"),
    RelType.INFLECTION: RelTypeLabel("infl.", "Inflection"),
}


_MAX_SECTION = 32_767


@dataclass(frozen=True, slots=True)
class Sense:
    """One originating Wiktextract entry's part of speech and gloss.

    Attributes:
        part_of_speech: Wiktextract's `pos`, when known.
        gloss: The entry's first gloss, or None.
    """

    part_of_speech: str | None = None
    gloss: str | None = None


@dataclass(frozen=True, slots=True)
class Term:
    """A headword in one language, as one occurrence names it.

    A term is a graph node; `section` and `variety_code` describe the
    occurrence, not the node, and land on the edge or sense row that
    carries them.

    Attributes:
        lang_code: The full language's Wiktionary code, never a variety.
        headword: Surface form, e.g. "aqua", "wréh₂ds" (star stripped).
        section: The "Etymology N" section this occurrence names, or 0
            when the source names none.
        is_reconstructed: True for a proto-form.
        variety_code: The etymology-only variety a template named (e.g.
            "la-lat"), or None.
        senses: The entry's own senses; empty for a template reference.
    """

    lang_code: str
    headword: str
    section: int = 0
    is_reconstructed: bool = False
    variety_code: str | None = None
    senses: tuple[Sense, ...] = ()

    def __post_init__(self) -> None:
        """Reject a section Postgres's SMALLINT can't hold.

        Raises:
            ValueError: If section is negative or above 32767.
        """
        if not 0 <= self.section <= _MAX_SECTION:
            msg = f"Term.section must be 0..{_MAX_SECTION}, got {self.section}"
            raise ValueError(msg)

    @property
    def key(self) -> tuple[str, str]:
        """The (lang_code, headword) pair deciding the node's identity."""
        return self.lang_code, self.headword


@dataclass(frozen=True, slots=True)
class EtymEdge:
    """A directed, typed, cited relation between two terms.

    Attributes:
        src: The ancestor occurrence.
        dst: The descendant occurrence (the entry whose page cites it).
        rel_type: The relation type.
        anchor: Where on the dst page the relation is stated, e.g.
            "etymology_templates:0:af" or "senses:2:form_of". Never empty.
        piece_order: The 1-based morpheme position, or None.
    """

    src: Term
    dst: Term
    rel_type: RelType
    anchor: str = ""
    piece_order: int | None = None

    def __post_init__(self) -> None:
        """Reject an uncited edge.

        Raises:
            ValueError: If anchor is empty.
        """
        if not self.anchor:
            msg = "EtymEdge.anchor must be non-empty (every edge is cited)"
            raise ValueError(msg)
