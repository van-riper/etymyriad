"""Pydantic models validating a raw Wiktextract dump entry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from etymyriad.model import _MAX_SECTION


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


class _WiktextractFormOf(BaseModel):
    """One raw sense's form_of record, as Wiktextract emits it."""

    model_config = ConfigDict(extra="ignore")

    word: str = ""


class _WiktextractSense(BaseModel):
    """One raw entry's sense, as Wiktextract emits it."""

    model_config = ConfigDict(extra="ignore")

    glosses: list[str] | None = None
    tags: list[str] = Field(default_factory=list)
    form_of: list[_WiktextractFormOf] = Field(default_factory=list)


class _WiktextractTemplate(BaseModel):
    """One raw etymology_templates record, as Wiktextract emits it."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    args: dict[str, str] = Field(default_factory=dict)


class _WiktextractEntry(BaseModel):
    """A validated Wiktextract dump entry, this module's untyped-JSON boundary.

    `lang_code` and `word` are required and non-empty: a dump entry
    missing either names no real word, and silently defaulting them
    to "" would build a bogus term node instead
    of failing loudly on malformed dump input.
    """

    model_config = ConfigDict(extra="ignore")

    lang_code: str = Field(min_length=1)
    word: str = Field(min_length=1)
    etymology_number: str | None = None
    original_title: str = ""
    pos: str | None = None
    senses: list[_WiktextractSense] = Field(default_factory=list)
    etymology_templates: list[_WiktextractTemplate] = Field(
        default_factory=list
    )

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
