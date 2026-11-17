"""Build `Term` objects from decoded Wiktextract entries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.languages import split_variety
from etymyriad.model import Sense, Term
from etymyriad.normalize._terms import (
    _add_affix_dash,
    _has_term,
    _strip_inline_annotation,
    _strip_star,
    _strip_wiktextract_markers,
)

if TYPE_CHECKING:
    from etymyriad.normalize._wiktextract import WiktextractEntry


def term_of_entry(entry: WiktextractEntry) -> Term:
    """Build the term an entry describes (the descendant side).

    Args:
        entry: A decoded Wiktextract entry.

    Returns:
        The term the entry describes.
    """
    lang_code, _ = split_variety(entry.lang_code)
    raw_word = _strip_wiktextract_markers(entry.word)
    headword, is_starred_or_proto = _strip_star(raw_word, lang_code)
    return Term(
        lang_code=lang_code,
        headword=headword,
        section=entry.section,
        is_reconstructed=is_starred_or_proto or entry.is_reconstruction_page,
        senses=(Sense(part_of_speech=entry.pos, gloss=entry.first_gloss),),
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


def _referenced_terms(
    raw_lang_code: str, raw_term: str, dash: str | None = None
) -> list[Term]:
    """Build one referenced term per alternant a reference lists.

    Wiktionary separates alternative forms of one reference with "//"
    (e.g. "try//trixhe//triche") and links each of them.

    Args:
        raw_lang_code: The ancestor's raw Wiktionary code (see
            `_referenced_term`).
        raw_term: The ancestor's term as written in the template.
        dash: A positionally-implied dash (see `_referenced_term`).

    Returns:
        One term per alternant that names a term, in order.
    """
    return [
        _referenced_term(raw_lang_code, alternant, dash)
        for alternant in _strip_inline_annotation(raw_term).split("//")
        if _has_term(alternant)
    ]


def referenced_term_key(raw_lang_code: str, raw_term: str) -> tuple[str, str]:
    """Return the node key a template reference resolves to.

    Args:
        raw_lang_code: The reference's raw Wiktionary language code.
        raw_term: The reference's term as written, possibly starred.

    Returns:
        The (language code, headword) pair that identifies the node.
    """
    return _referenced_term(raw_lang_code, raw_term).key
