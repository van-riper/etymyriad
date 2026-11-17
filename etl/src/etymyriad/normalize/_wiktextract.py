"""Typed msgspec Structs for a raw Wiktextract dump entry.

Decoding a dump line straight into `WiktextractEntry` skips every field
the normalizer never reads, and encoding one back out is how `filter`
trims the dump.
"""

from typing import TYPE_CHECKING, Annotated, get_args

import msgspec

from etymyriad.model import _MAX_SECTION

if TYPE_CHECKING:
    from collections.abc import Iterator

type _NonEmptyText = Annotated[str, msgspec.Meta(min_length=1)]


def _section_of(raw: str | None) -> int:
    """Parse Wiktextract's etymology_number, falling back to 0.

    A value that isn't a plain number Postgres's SMALLINT can hold is
    treated as unnumbered rather than failing the entry.

    Returns:
        The section number, or 0.
    """
    if raw is None or not (raw.isascii() and raw.isdigit()):
        return 0
    if int(raw) > _MAX_SECTION:
        return 0
    return int(raw)


class _WiktextractFormOf(msgspec.Struct, omit_defaults=True):
    """One raw sense's form_of record, as Wiktextract emits it."""

    word: str = ""


class _WiktextractSense(msgspec.Struct, omit_defaults=True):
    """One raw entry's sense, as Wiktextract emits it.

    `senseid` holds the sense's {{senseid}} ids, prefixed
    "<lang_code>:".
    """

    glosses: list[str] | None = None
    tags: list[str] = []
    form_of: list[_WiktextractFormOf] = []
    senseid: list[str] = []


class _WiktextractTemplate(msgspec.Struct, omit_defaults=True):
    """One raw etymology_templates record, as Wiktextract emits it."""

    name: str = ""
    args: dict[str, str] = {}


class _WiktextractLinkedTerm(msgspec.Struct, omit_defaults=True):
    """One Descendants or Derived terms item, as Wiktextract emits it."""

    word: str = ""
    lang_code: str = ""
    descendants: list[_WiktextractLinkedTerm] = []


class WiktextractEntry(msgspec.Struct, omit_defaults=True):
    """A decoded Wiktextract dump entry, the ETL's untyped-JSON boundary.

    `word` and `lang_code` are required and non-empty: a dump entry
    missing either names no real word, and silently defaulting them to
    "" would build a bogus term node instead of failing loudly on
    malformed dump input.

    Attributes:
        word: The entry's headword.
        lang_code: The entry's Wiktionary language code.
        etymology_number: The raw "Etymology N" number, if any.
        original_title: The page title, namespace included.
        pos: The part of speech.
        senses: The entry's senses.
        etymology_templates: The templates its etymology section uses.
        descendants: Its Descendants list, nested.
        derived: Its Derived terms list.
    """

    word: _NonEmptyText
    lang_code: _NonEmptyText
    etymology_number: str | None = None
    original_title: str = ""
    pos: str | None = None
    senses: list[_WiktextractSense] = []
    etymology_templates: list[_WiktextractTemplate] = []
    descendants: list[_WiktextractLinkedTerm] = []
    derived: list[_WiktextractLinkedTerm] = []

    @property
    def section(self) -> int:
        """The entry's etymology section number, 0 when unnumbered."""
        return _section_of(self.etymology_number)

    @property
    def is_reconstruction_page(self) -> bool:
        """Whether the entry lives in Wiktionary's Reconstruction namespace."""
        return self.original_title.startswith("Reconstruction:")

    @property
    def first_gloss(self) -> str | None:
        """The first sense's first gloss, or None if there is none."""
        for sense in self.senses:
            if sense.glosses:
                return sense.glosses[0]
        return None


def _struct_in(annotation: object) -> type[msgspec.Struct] | None:
    """Find the Struct an annotation names, at any depth.

    Returns:
        The Struct, or None for an annotation of plain values.
    """
    if isinstance(annotation, type) and issubclass(annotation, msgspec.Struct):
        return annotation
    return next(filter(None, map(_struct_in, get_args(annotation))), None)


def field_paths() -> frozenset[str]:
    """Every dotted field path `WiktextractEntry` decodes.

    A path stops where a Struct repeats on it, so a recursive
    `descendants` list ends at "descendants.descendants".

    Returns:
        Paths such as "senses.form_of.word".
    """
    return frozenset(_paths_under(WiktextractEntry, "", frozenset()))


def _paths_under(
    struct: type[msgspec.Struct],
    prefix: str,
    ancestors: frozenset[type[msgspec.Struct]],
) -> Iterator[str]:
    """Yield the paths below `struct`, cutting at a repeated Struct."""
    lineage = ancestors | {struct}
    for field in msgspec.structs.fields(struct):
        path = f"{prefix}{field.name}"
        yield path
        child = _struct_in(field.type)
        if child is not None and child not in lineage:
            yield from _paths_under(child, f"{path}.", lineage)
