"""The graph model. Mirrors `db/schema.sql` exactly.

A `Lexeme` is a node. An `EtymEdge` is a directed ancestor -> descendant
relation. Both are frozen so they can be deduplicated in sets before loading.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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
    COGNATE = "cognate"
    MENTION = "mention"
    ONOMATOPOEIC = "onomatopoeic"


@dataclass(frozen=True, slots=True)
class Sense:
    """One originating Wiktextract entry's pos/gloss, attached to a lexeme.

    A lexeme now groups by etymology_number rather than by gloss/pos, so a
    single lexeme (e.g. "reverse" adj/adv/noun, one shared derivation)
    can carry more than one sense.

    Attributes:
        pos: Part of speech, when known.
        gloss: Short sense description, or None.
        source_ref: Wiktionary page or dump provenance. Never empty.
    """

    pos: str | None = None
    gloss: str | None = None
    source_ref: str = ""

    def __post_init__(self) -> None:
        """Reject an unsourced sense.

        Raises:
            ValueError: If source_ref is empty.
        """
        if not self.source_ref:
            msg = "Sense.source_ref must be non-empty (nothing is unsourced)"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Lexeme:
    """A word or morpheme in a single language (a graph node).

    The surrogate id is assigned by the database and is not modeled here.

    Attributes:
        lang_code: Wiktionary language code, e.g. "en", "la", "ine-pro".
        headword: Surface form, e.g. "etymology", "aqua", "*wréh₂ds".
        etymology_number: Wiktextract's own sense-grouping number (a string
            like "1", "2"), or None when a page has one implicit,
            unnumbered etymology section. This, not gloss/pos, is the
            correct signal for node identity.
        romanization: Romanized form for a non-Latin script, or None.
        is_reconstructed: True for a proto-form (a leading "*").
        source_ref: Wiktionary page or dump provenance. Never empty.
        senses: The originating entries' pos/gloss, merged onto this node.
    """

    lang_code: str
    headword: str
    etymology_number: str | None = None
    romanization: str | None = None
    is_reconstructed: bool = False
    source_ref: str = ""
    senses: tuple[Sense, ...] = ()

    def __post_init__(self) -> None:
        """Reject an unsourced lexeme.

        Raises:
            ValueError: If source_ref is empty.
        """
        if not self.source_ref:
            msg = "Lexeme.source_ref must be non-empty (nothing is unsourced)"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EtymEdge:
    """A directed, typed, cited relation between two lexemes (a graph edge).

    An edge is unique on (src, dst, rel_type), and src and dst differ.

    Attributes:
        src: The ancestor (source) lexeme.
        dst: The descendant lexeme.
        rel_type: The relation type (see RelType).
        source_ref: Wiktionary page or template provenance. Never empty.
    """

    src: Lexeme
    dst: Lexeme
    rel_type: RelType
    source_ref: str = ""

    def __post_init__(self) -> None:
        """Reject an unsourced edge.

        Raises:
            ValueError: If source_ref is empty.
        """
        if not self.source_ref:
            msg = "EtymEdge.source_ref must be non-empty (every edge is cited)"
            raise ValueError(msg)
