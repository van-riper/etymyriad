"""Language and language-set records, linked into one navigable tree."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

type LanguageCode = str
type SetCode = str
type WikidataQid = int


class LanguageKind(StrEnum):
    """What a Wiktionary code names.

    The first three mirror Module:languages' own `type` field. A
    variety is an etymology-only lect with no entries of its own. A
    collective is a family code standing for "some language of this
    set", as in {{der|en|gem}}.
    """

    REGULAR = "regular"
    RECONSTRUCTED = "reconstructed"
    CONSTRUCTED = "appendix-constructed"
    VARIETY = "variety"
    COLLECTIVE = "collective"


@dataclass(frozen=True, slots=True)
class LanguageSet:
    """A Wiktionary family: a genetic, areal, or catch-all grouping.

    Attributes:
        code: Wiktionary family code, e.g. "gmw" or "cel-bry".
        name: English canonical name, e.g. "West Germanic".
        superset: The enclosing set, or None at a root such as "ine".
        proto_language_code: The language this set descends from, e.g.
            "gem-pro" for "gem" or "la" for "roa", when Wiktionary
            names one.
        wikidata_qid: Wikidata item number, e.g. 26721 for Q26721.
        iso639_5: The family code itself, when Wikidata confirms it is
            an ISO 639-5 code.
    """

    code: SetCode
    name: str
    superset: LanguageSet | None = None
    proto_language_code: LanguageCode | None = None
    wikidata_qid: WikidataQid | None = None
    iso639_5: str | None = None

    @property
    def lineage(self) -> tuple[LanguageSet, ...]:
        """Every set from the root down to this one."""
        if self.superset is None:
            return (self,)
        return (*self.superset.lineage, self)

    @property
    def path(self) -> tuple[SetCode, ...]:
        """The codes of `lineage`, root first."""
        return tuple(language_set.code for language_set in self.lineage)

    @property
    def hierarchy(self) -> str:
        """The path joined ISO 639-5 style, e.g. "ine:gem:gmw"."""
        return ":".join(self.path)


@dataclass(frozen=True, slots=True)
class Language:
    """One code an entry or etymology template can name.

    Attributes:
        code: Wiktionary code, e.g. "en", "gem-pro", "la-lat", "gem".
        name: English canonical name.
        kind: What the code names; see LanguageKind.
        language_set: The set this language belongs to. A variety
            inherits its full language's set and a collective is its
            own set. None when Wiktionary assigns no family.
        parent: For a variety, the language or variety it belongs to.
        is_reconstructed: True for a proto-language or proto-variety.
        wikidata_qid: Wikidata item number, when Wiktionary records one.
        scripts: ISO 15924 script codes Wiktionary lists, primary first.
        wikimedia_codes: Wikipedia/Wikimedia project codes, when
            Wiktionary records ones that differ from its own.
        iso639_1: Two-letter ISO 639-1 code.
        iso639_2b: ISO 639-2 bibliographic code, where it differs from
            the terminological one (e.g. "fre" for French).
        iso639_3: ISO 639-3 code (e.g. "eng" for "en", "hbs" for "sh").
    """

    code: LanguageCode
    name: str
    kind: LanguageKind
    language_set: LanguageSet | None = None
    parent: Language | None = None
    is_reconstructed: bool = False
    wikidata_qid: WikidataQid | None = None
    scripts: tuple[str, ...] = ()
    wikimedia_codes: tuple[str, ...] = ()
    iso639_1: str | None = None
    iso639_2b: str | None = None
    iso639_3: str | None = None

    @property
    def full_language(self) -> Language:
        """The non-variety language whose entries hold this code's terms."""
        if self.parent is None:
            return self
        return self.parent.full_language
