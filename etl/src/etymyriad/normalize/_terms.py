"""Pure term/language-code string helpers with no model dependency."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from etymyriad.model import PROTO_LANG_SUFFIX

if TYPE_CHECKING:
    from collections.abc import Iterator

# Wiktextract's own internal placeholder characters, used to protect
# link/nowiki spans mid-parse. They belong to the Supplementary Private Use
# Area-A block (U+F0000-FFFFD) and have no glyph by definition, so they must
# never survive into a stored headword/term.
_WIKTEXTRACT_MARKER_RE = re.compile(r"[\U000f0000-\U000ffffd]")


def _strip_wiktextract_markers(raw: str) -> str:
    """Drop Wiktextract's internal PUA-A placeholder characters.

    Args:
        raw: A headword or term, possibly carrying leftover markers.

    Returns:
        `raw` with every such marker removed.
    """
    return _WIKTEXTRACT_MARKER_RE.sub("", raw)


def _strip_star(raw: str, lang_code: str) -> tuple[str, bool]:
    """Strip a leading reconstruction star and flag reconstructed forms.

    Kaikki stores proto own-entries starless but references them with a
    leading "*"; stripping it unifies both onto one lexeme node.

    Args:
        raw: A headword or term, possibly starred.
        lang_code: The term's Wiktionary language code.

    Returns:
        The unstarred form and whether it is reconstructed.
    """
    is_starred = raw.startswith("*")
    headword = raw[1:] if is_starred else raw
    return headword, is_starred or lang_code.endswith(PROTO_LANG_SUFFIX)


def _strip_inline_annotation(raw: str) -> str:
    """Drop a trailing "<...>" annotation, e.g. "<id:away>" or "<unc>".

    Returns:
        The text before the first "<", or the whole string if there is none.
    """
    return raw.split("<", 1)[0]


def _has_term(raw: str) -> bool:
    """Whether a raw term argument names an actual attested term.

    Wiktionary editors write a literal "-" to assert a relation/language
    without naming a specific term (e.g. {{der|en|la|-}}). Wiktextract
    passes it through unchanged, so it must be treated the same as an
    absent argument. Left unhandled, every such template collapses onto
    one bogus "-" lexeme node per language.

    Args:
        raw: A raw term argument.

    Returns:
        Whether `raw` names a real term.
    """
    return bool(raw) and raw != "-"


def _add_affix_dash(headword: str, side: str) -> str:
    """Add a positionally-implied dash a bare affix morpheme is missing.

    {{suffix}}/{{suf}}/{{prefix}}/{{infix}} each glue one morpheme onto a
    fixed side of an exempt "base" piece, so Wiktionary's own rendering
    infers and adds the dash even when an editor writes the raw template
    arg bare (confirmed by Wiktextract's precomputed "expansion" field:
    {{suf|en|linguist|ic}} expands to "linguist + -ic" although the raw
    arg is bare "ic"). Leaving it unadded creates a bogus lexeme node
    distinct from the real, dashed dictionary entry.

    Args:
        headword: The morpheme's headword, already destarred.
        side: "leading", "trailing", or "both".

    Returns:
        `headword` with the missing dash(es) added; a dash already
        present is left alone.
    """
    if side in {"leading", "both"} and not headword.startswith("-"):
        headword = f"-{headword}"
    if side in {"trailing", "both"} and not headword.endswith("-"):
        headword = f"{headword}-"
    return headword


# Wiktionary editors sometimes write these Latin-period abbreviations
# directly as a directional template's ancestor-language argument (e.g.
# {{bor|ca|EL.|reliquiarium}}), instead of the canonical Wiktextract code
# that appears everywhere else in the dataset for the same period.
_LATIN_PERIOD_SHORTHAND: dict[str, str] = {
    "EL.": "la-ecc",  # Ecclesiastical Latin
    "LL.": "la-lat",  # Late Latin
    "ML.": "la-med",  # Medieval Latin
    "NL.": "la-new",  # New Latin
    "VL.": "la-vul",  # Vulgar Latin
}


# A plausible Wiktionary language code (e.g. "en", "gem-pro", "en-US"), not
# arbitrary text that happens to contain a colon: a parenthetical gloss
# ("Forum (plural: Foren)") or a wiki-interlink marker ("w:WikiWikiWeb", a
# cross-reference to an English Wikipedia article, not a language). No real
# Wiktionary language code is a single letter, which is what excludes "w".
_LANG_CODE_RE = re.compile(r"^[a-z][a-z0-9]+(-[A-Za-z0-9]+)*$")


def _lang_and_term(raw: str, default_lang: str) -> tuple[str, str]:
    """Split a term that may carry an explicit "lang:" prefix.

    Strips any trailing "<...>" annotation first, since annotations (e.g.
    "<id:away>") themselves contain colons that would otherwise be mistaken
    for the lang/term separator. A colon is only treated as a lang/term
    separator when the text before it actually looks like a language code,
    or is one of Wiktionary's dotted Latin-period shorthands (e.g. "NL.",
    see `_LATIN_PERIOD_SHORTHAND`). Those start uppercase, so they fail
    `_LANG_CODE_RE` on purpose and need their own check. Otherwise the
    colon is just part of the term itself (e.g. "Forum (plural: Foren)", a
    parenthetical gloss), and splitting on it would manufacture a bogus
    ancestor language.

    Args:
        raw: A term, possibly annotated and/or lang-prefixed.
        default_lang: The language to use when `raw` carries no prefix.

    Returns:
        The ancestor's language code and its unannotated term.
    """
    stripped = _strip_inline_annotation(raw)
    if ":" in stripped:
        lang_code, _, term = stripped.partition(":")
        if lang_code in _LATIN_PERIOD_SHORTHAND:
            return _LATIN_PERIOD_SHORTHAND[lang_code], term
        if _LANG_CODE_RE.match(lang_code):
            return lang_code, term
    return default_lang, stripped


def _split_lang_codes(raw: str) -> list[str]:
    """Split a possibly comma-joined language-code argument.

    Wiktionary templates sometimes give a directional relation's ancestor
    language as a comma-joined list (e.g. "pt-BR,de"), meaning the same term
    is asserted as a cognate borrowing shared by each language, not one
    language whose code happens to contain a comma.

    Args:
        raw: A template's raw language-code argument.

    Returns:
        Each non-empty, whitespace-stripped code, in order.
    """
    return [code.strip() for code in raw.split(",") if code.strip()]


def _affix_family_pieces(
    args: dict[str, str], offset: int = 0
) -> Iterator[tuple[int, str]]:
    """Yield each present morpheme term of a same-language affix template.

    Positions start at args["2"]; "altN" (1-based per morpheme) overrides
    the Nth positional term when both are given. A missing or empty piece
    (a morpheme Wiktionary could not identify) is skipped, but still
    counts toward the piece number: a template's dash convention (see
    `_AFFIX_HYPHEN_SIDE`) is positional on the *slot*, not on the
    surviving pieces' own order.

    Args:
        args: The template's raw argument mapping.
        offset: Extra positions to skip before args["2"]: 1 for a
            {{surf}} call carrying a leading "+type" flag (see
            `_edges_from_entry`), 0 otherwise. "altN" is unaffected: it
            is 1-based per morpheme regardless of where the positional
            args start.

    Yields:
        Each non-empty morpheme term with its 1-based piece number.
    """
    piece = 1
    while str(piece + 1 + offset) in args:
        raw = args.get(f"alt{piece}") or args.get(str(piece + 1 + offset), "")
        if _has_term(raw):
            yield piece, raw
        piece += 1


def _affix_piece_count(args: dict[str, str], offset: int = 0) -> int:
    """Count an affix-family template's total morpheme slots.

    Counts every slot from args["2"] on, including an empty one (a
    morpheme Wiktionary could not identify); {{prefix}}'s dash
    convention exempts the *last* slot regardless of emptiness elsewhere.

    Args:
        args: The template's raw argument mapping.
        offset: Extra positions to skip before args["2"] (see
            `_affix_family_pieces`).

    Returns:
        The total number of morpheme slots.
    """
    count = 0
    while str(count + 2 + offset) in args:
        count += 1
    return count


def _surf_type_flag_lang(flag: str, entry_lang: str) -> str | None:
    """Resolve the language a {{surf}} "+type" flag implies, if any.

    {{surf}}'s optional leading "+type" flag (e.g. "+suf", "+deverbal")
    shifts the language from args["1"] to args["2"], but a minority of
    "+type" flags are themselves language-specific formation labels
    written "+<lang>-<description>" (e.g. "+it-deverbal" for an Italian
    deverbal noun), which carry no separate language argument at all: the
    pieces that follow are already in the entry's own language.
    Wiktextract's own "expansion" field never names a different language
    for these, confirming the label doesn't shift anything: args["2"]
    onward are the same positions an unflagged {{surf}} call would use.

    Args:
        flag: The "+"-prefixed args["1"] value.
        entry_lang: The entry's own Wiktionary language code.

    Returns:
        `entry_lang` if `flag` names it as a formation label, else None
        (a generic flag, whose language comes from args["2"] instead).
    """
    prefix, _, rest = flag[1:].partition("-")
    return entry_lang if rest and prefix == entry_lang else None


def _affix_family_lang_and_offset(
    name: str, args: dict[str, str], entry_lang: str
) -> tuple[str, int]:
    """Resolve an affix-family template's language and its piece offset.

    Every affix-family template but {{surf}} always carries the
    language bare in args["1"], with pieces from args["2"] on (offset
    0). {{surf}} adds its optional leading "+type" flag (see
    `_surf_type_flag_lang`): a generic flag shifts the language to
    args["2"] and pieces to args["3"] on (offset 1); a language-specific
    flag names no separate language argument, so it resolves like the
    no-flag case (offset 0) with the entry's own language substituted
    for args["1"].

    Args:
        name: The template's name.
        args: The template's raw argument mapping.
        entry_lang: The entry's own Wiktionary language code.

    Returns:
        The ancestor pieces' language code (possibly empty) and the
        offset `_affix_piece_count`/`_affix_family_pieces` need.
    """
    raw_arg1 = args.get("1", "")
    if name == "surf" and raw_arg1.startswith("+"):
        lang_code = _surf_type_flag_lang(raw_arg1, entry_lang)
        if lang_code is not None:
            return lang_code, 0
        return args.get("2", ""), 1
    return raw_arg1, 0


# Which side of an affix-family piece carries a positionally-implied dash
# (see `_add_affix_dash`). {{affix}}/{{af}}/{{com}}/{{compound}} carry no
# such convention: a piece may be a prefix, root, or suffix in any
# position, so editors must and do write the dash themselves. They are
# absent from this table on purpose.
_AFFIX_HYPHEN_SIDE: dict[str, str] = {
    "prefix": "trailing",
    "suffix": "leading",
    "suf": "leading",
    "infix": "both",
}


def _affix_base_piece(name: str, piece_count: int) -> int:
    """Return the 1-based piece number exempt from the dash convention.

    {{prefix}}'s base (the word the prefix chain attaches to) is its
    *last* piece; {{suffix}}/{{suf}}/{{infix}}'s base is always their
    first.

    Args:
        name: The template's name.
        piece_count: The template's total morpheme slot count.

    Returns:
        The exempt piece number.
    """
    return piece_count if name == "prefix" else 1
