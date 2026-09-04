"""Build `Lexeme` objects from validated Wiktextract entries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.model import Lexeme, Sense
from etymyriad.normalize._terms import (
    _LATIN_PERIOD_SHORTHAND,
    _add_affix_dash,
    _strip_inline_annotation,
    _strip_star,
    _strip_wiktextract_markers,
)
from etymyriad.normalize._wiktextract import _WiktextractEntry

if TYPE_CHECKING:
    from collections.abc import Mapping


def lexeme_of_entry(entry: Mapping[str, object], dump_date: str) -> Lexeme:
    """Build the lexeme an entry describes (the descendant side).

    Args:
        entry: A parsed Wiktextract entry.
        dump_date: The enwiktionary dump date, pinned into source_ref.

    Returns:
        The lexeme the entry describes.
    """
    return _lexeme_of_parsed(_WiktextractEntry.model_validate(entry), dump_date)


def _lexeme_of_parsed(parsed: _WiktextractEntry, dump_date: str) -> Lexeme:
    """Build the lexeme a validated entry describes.

    Args:
        parsed: A validated Wiktextract entry.
        dump_date: The enwiktionary dump date, pinned into source_ref.

    Returns:
        The lexeme the entry describes.
    """
    lang_code = parsed.lang_code
    raw_word = _strip_wiktextract_markers(parsed.word)
    headword, is_reconstructed = _strip_star(raw_word, lang_code)
    source_ref = f"wiktionary:{dump_date}:{lang_code}:{headword}"
    sense = Sense(
        pos=parsed.pos,
        gloss=parsed.first_gloss,
        source_ref=source_ref,
    )

    return Lexeme(
        lang_code=lang_code,
        headword=headword,
        etymology_number=parsed.etymology_number,
        is_reconstructed=is_reconstructed,
        source_ref=source_ref,
        senses=(sense,),
    )


def _referenced_lexeme(
    lang_code: str,
    raw_term: str,
    dump_date: str,
    dash: str | None = None,
) -> Lexeme:
    """Build the lexeme an etymology template points at (the ancestor side).

    Referenced lexemes carry no etymology_number and no senses: a
    template's inline gloss describes the sense relevant to that one
    etymology, not the ancestor's own canonical first sense, so recording
    it here would fragment the natural key away from the node built when
    the ancestor's own entry is parsed. They default to is_redlink=True
    for the same reason: a template gives no way to tell whether the
    ancestor has its own entry elsewhere in the dump, so the loader's
    upsert clears the flag if and when that entry loads.

    Args:
        lang_code: The ancestor's Wiktionary language code, or a Latin-
            period editor shorthand (e.g. "EL.") resolved to its canonical
            code here.
        raw_term: The ancestor's term as written in the template, possibly
            starred and/or carrying a trailing "<...>" annotation (e.g.
            "un-<id:reversive>").
        dump_date: The enwiktionary dump date, pinned into source_ref.
        dash: "leading", "trailing", "both", or None: a positionally-
            implied dash to add to the headword if missing (see
            `_add_affix_dash`).

    Returns:
        The referenced lexeme, keyed on the canonical language code.
    """
    lang_code = _LATIN_PERIOD_SHORTHAND.get(lang_code, lang_code)
    term = _strip_wiktextract_markers(_strip_inline_annotation(raw_term))
    headword, is_reconstructed = _strip_star(term, lang_code)
    if dash is not None:
        headword = _add_affix_dash(headword, dash)
    return Lexeme(
        lang_code=lang_code,
        headword=headword,
        is_reconstructed=is_reconstructed,
        is_redlink=True,
        source_ref=f"wiktionary:{dump_date}:{lang_code}:{headword}",
    )
