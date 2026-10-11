"""Build `Term` objects from validated Wiktextract entries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.languages import split_variety
from etymyriad.model import Sense, Term
from etymyriad.normalize._terms import (
    _add_affix_dash,
    _strip_inline_annotation,
    _strip_star,
    _strip_wiktextract_markers,
)
from etymyriad.normalize._wiktextract import _WiktextractEntry

if TYPE_CHECKING:
    from collections.abc import Mapping


def term_of_entry(entry: Mapping[str, object]) -> Term:
    """Build the term an entry describes (the descendant side).

    Args:
        entry: A parsed Wiktextract entry.

    Returns:
        The term the entry describes.
    """
    return _term_of_parsed(_WiktextractEntry.model_validate(entry))


def _term_of_parsed(parsed: _WiktextractEntry) -> Term:
    """Build the term a validated entry describes.

    Args:
        parsed: A validated Wiktextract entry.

    Returns:
        The term the entry describes.
    """
    lang_code, _ = split_variety(parsed.lang_code)
    raw_word = _strip_wiktextract_markers(parsed.word)
    headword, is_starred_or_proto = _strip_star(raw_word, lang_code)
    return Term(
        lang_code=lang_code,
        headword=headword,
        section=parsed.section,
        is_reconstructed=is_starred_or_proto or parsed.is_reconstruction_page,
        senses=(Sense(part_of_speech=parsed.pos, gloss=parsed.first_gloss),),
    )


def _referenced_term(
    raw_lang_code: str, raw_term: str, dash: str | None = None
) -> Term:
    """Build the term an etymology template points at (the ancestor side).

    A reference carries no section (templates don't name one without
    `<id:>`, which isn't resolved yet) and no senses: its inline gloss
    describes this one etymology, not the ancestor's own entry.

    Args:
        raw_lang_code: The ancestor's raw Wiktionary code, Latin-period
            shorthand (e.g. "EL."), or drifted code, resolved here.
        raw_term: The ancestor's term as written in the template, possibly
            starred and/or carrying a trailing "<...>" annotation (e.g.
            "un-<id:reversive>").
        dash: "leading", "trailing", "both", or None: a positionally-
            implied dash to add to the headword if missing (see
            `_add_affix_dash`).

    Returns:
        The referenced term, filed under its full language with any
        etymology-only variety recorded separately.
    """
    language_code, variety_code = split_variety(raw_lang_code)
    term = _strip_wiktextract_markers(_strip_inline_annotation(raw_term))
    headword, is_reconstructed = _strip_star(
        term, variety_code or language_code
    )
    if dash is not None:
        headword = _add_affix_dash(headword, dash)
    return Term(
        lang_code=language_code,
        headword=headword,
        is_reconstructed=is_reconstructed,
        variety_code=variety_code,
    )


def referenced_term_key(raw_lang_code: str, raw_term: str) -> tuple[str, str]:
    """Return the node key a template reference resolves to.

    Args:
        raw_lang_code: The reference's raw Wiktionary language code.
        raw_term: The reference's term as written, possibly starred.

    Returns:
        The (language code, headword) pair that identifies the node.
    """
    return _referenced_term(raw_lang_code, raw_term).key
