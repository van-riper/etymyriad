"""Pydantic models validating a raw Wiktextract dump entry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
    to "" would build a bogus, unsourced-looking lexeme node instead
    of failing loudly on malformed dump input.
    """

    model_config = ConfigDict(extra="ignore")

    lang_code: str = Field(min_length=1)
    word: str = Field(min_length=1)
    etymology_number: str | None = None
    pos: str | None = None
    senses: list[_WiktextractSense] = Field(default_factory=list)
    etymology_templates: list[_WiktextractTemplate] = Field(
        default_factory=list
    )

    @property
    def first_gloss(self) -> str | None:
        """The first sense's first gloss, or None if there is none."""
        for sense in self.senses:
            if sense.glosses:
                return sense.glosses[0]
        return None
