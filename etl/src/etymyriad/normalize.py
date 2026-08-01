"""Map raw Wiktextract entries to graph objects.

Each Wiktextract entry describes one word and carries `etymology_templates`:
structured records of the {{inh}}, {{bor}}, {{der}}, ... templates used on the
page. We translate those into directed `EtymEdge`s (ancestor -> the entry's own
lexeme).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from etymyriad.model import (
    PROTO_LANG_SUFFIX,
    EtymEdge,
    Lexeme,
    RelType,
    Sense,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

# Wiktextract template name -> our relation type.
TEMPLATE_REL_TYPES: dict[str, RelType] = {
    "inh": RelType.INHERITED,
    "inherited": RelType.INHERITED,
    "inh+": RelType.INHERITED,
    "bor": RelType.BORROWED,
    "borrowed": RelType.BORROWED,
    "bor+": RelType.BORROWED,
    "lbor": RelType.LEARNED_BORROWING,
    "slbor": RelType.SEMI_LEARNED_BORROWING,
    "der": RelType.DERIVED,
    "derived": RelType.DERIVED,
    "root": RelType.ROOT,
    "af": RelType.AFFIX,
    "affix": RelType.AFFIX,
    "prefix": RelType.AFFIX,
    "suffix": RelType.AFFIX,
    "suf": RelType.AFFIX,
    "infix": RelType.AFFIX,
    "com": RelType.COMPOUND,
    "compound": RelType.COMPOUND,
    "cal": RelType.CALQUE,
    "calque": RelType.CALQUE,
    "cog": RelType.COGNATE,
    "cognate": RelType.COGNATE,
    "m": RelType.MENTION,
    "mention": RelType.MENTION,
    "m+": RelType.MENTION,
}


@dataclass(frozen=True, slots=True)
class _TemplateContext:
    """Provenance shared by every edge a single template call produces."""

    dst: Lexeme
    dump_date: str
    source_ref: str


# Directional templates: args["1"] is the entry's own language, args["2"] is
# the ancestor's language. The ancestor's term is args["4"] (an attested form)
# when present, else args["3"] (which may be a bound root) -- Wiktionary's own
# expansion text prefers args["4"] the same way whenever both are given.
_DIRECTIONAL_TEMPLATES = frozenset({
    "inh",
    "inherited",
    "inh+",
    "bor",
    "borrowed",
    "bor+",
    "lbor",
    "slbor",
    "der",
    "derived",
    "root",
    "cal",
    "calque",
})

# {{etymon}} (and its older alias {{ety}}) encode their relation and term
# differently from the directional templates: the sub-relation is a
# ":code" in args["2"] (e.g. ":inh", ":der<unc>"), with the term in
# args["3"]; a bare args["2"] with no leading colon is itself the term, in
# the entry's own language, and asserts only a generic "derived from".
# "from" and "vrd" (vrddhi derivation) are etymon-only codes with no
# standalone template of their own, so they carry no direct
# template->relation mapping.
_ETYMON_SUB_REL_TYPES: dict[str, RelType] = {
    "inh": RelType.INHERITED,
    "bor": RelType.BORROWED,
    "lbor": RelType.LEARNED_BORROWING,
    "slbor": RelType.SEMI_LEARNED_BORROWING,
    "der": RelType.DERIVED,
    "from": RelType.DERIVED,
    "vrd": RelType.DERIVED,
    "root": RelType.ROOT,
    "af": RelType.AFFIX,
}

# Same-language, multi-morpheme templates: args["1"] is shared by every
# morpheme (no per-piece ancestor language), and each morpheme lives at a
# consecutive position starting at args["2"]. "altN" (1-based per morpheme)
# overrides the Nth positional term when both are given, the same way the
# directional family's args["4"] overrides args["3"].
_AFFIX_FAMILY_TEMPLATES = frozenset({
    "af",
    "affix",
    "prefix",
    "suffix",
    "suf",
    "infix",
    "com",
    "compound",
})

# {{m}}/{{mention}}/{{m+}} cite a same-page mention rather than a structural
# derivation: args["1"] is the mentioned term's own language, args["2"] its
# term, with args["3"] (when present) overriding it the same way "altN"
# overrides a base term elsewhere.
_MENTION_TEMPLATES = frozenset({"m", "mention", "m+"})


def normalize(
    entries: Iterable[Mapping[str, object]],
    dump_date: str,
) -> Iterator[EtymEdge]:
    """Yield etymology edges for every entry in the stream.

    Args:
        entries: Parsed Wiktextract entries.
        dump_date: The dump date pinned into each edge's provenance.

    Yields:
        The etymology edges the stream produces.
    """
    for entry in entries:
        yield from _edges_from_entry(entry, dump_date)


def lexeme_of_entry(entry: Mapping[str, object], dump_date: str) -> Lexeme:
    """Build the lexeme an entry describes (the descendant side).

    Args:
        entry: A parsed Wiktextract entry.
        dump_date: The enwiktionary dump date, pinned into source_ref.

    Returns:
        The lexeme the entry describes.
    """
    lang_code = cast("str", entry.get("lang_code", ""))
    raw_word = _strip_wiktextract_markers(cast("str", entry.get("word", "")))
    headword, is_reconstructed = _strip_star(raw_word, lang_code)
    etymology_number = cast("str | None", entry.get("etymology_number"))
    source_ref = f"wiktionary:{dump_date}:{lang_code}:{headword}"
    sense = Sense(
        pos=cast("str | None", entry.get("pos")),
        gloss=_first_gloss(entry),
        source_ref=source_ref,
    )

    return Lexeme(
        lang_code=lang_code,
        headword=headword,
        etymology_number=etymology_number,
        is_reconstructed=is_reconstructed,
        source_ref=source_ref,
        senses=(sense,),
    )


def _referenced_lexeme(lang_code: str, raw_term: str, dump_date: str) -> Lexeme:
    """Build the lexeme an etymology template points at (the ancestor side).

    Referenced lexemes carry no etymology_number and no senses: a
    template's inline gloss describes the sense relevant to that one
    etymology, not the ancestor's own canonical first sense, so recording
    it here would fragment the natural key away from the node built when
    the ancestor's own entry is parsed.

    Args:
        lang_code: The ancestor's Wiktionary language code, or a Latin-
            period editor shorthand (e.g. "EL.") resolved to its canonical
            code here.
        raw_term: The ancestor's term as written in the template, possibly
            starred and/or carrying a trailing "<...>" annotation (e.g.
            "un-<id:reversive>").
        dump_date: The enwiktionary dump date, pinned into source_ref.

    Returns:
        The referenced lexeme, keyed on the canonical language code.
    """
    lang_code = _LATIN_PERIOD_SHORTHAND.get(lang_code, lang_code)
    term = _strip_wiktextract_markers(_strip_inline_annotation(raw_term))
    headword, is_reconstructed = _strip_star(term, lang_code)
    return Lexeme(
        lang_code=lang_code,
        headword=headword,
        is_reconstructed=is_reconstructed,
        source_ref=f"wiktionary:{dump_date}:{lang_code}:{headword}",
    )


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


def _first_gloss(entry: Mapping[str, object]) -> str | None:
    """Return the first sense's first gloss, or None if there is none."""
    senses = cast("list[Mapping[str, object]]", entry.get("senses", []))
    for sense in senses:
        glosses = cast("list[str] | None", sense.get("glosses"))
        if glosses:
            return glosses[0]
    return None


def _strip_inline_annotation(raw: str) -> str:
    """Drop a trailing "<...>" annotation, e.g. "<id:away>" or "<unc>".

    Returns:
        The text before the first "<", or the whole string if there is none.
    """
    return raw.split("<", 1)[0]


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
# arbitrary text that happens to contain a colon -- a parenthetical gloss
# ("Forum (plural: Foren)") or a wiki-interlink marker ("w:WikiWikiWeb", a
# cross-reference to an English Wikipedia article, not a language). No real
# Wiktionary language code is a single letter, which is what excludes "w".
_LANG_CODE_RE = re.compile(r"^[a-z][a-z0-9]+(-[A-Za-z0-9]+)*$")


def _lang_and_term(raw: str, default_lang: str) -> tuple[str, str]:
    """Split a term that may carry an explicit "lang:" prefix.

    Strips any trailing "<...>" annotation first, since annotations (e.g.
    "<id:away>") themselves contain colons that would otherwise be mistaken
    for the lang/term separator. A colon is only treated as a lang/term
    separator when the text before it actually looks like a language code --
    otherwise it is just a term with its own embedded colon (e.g. "Forum
    (plural: Foren)", a parenthetical gloss), and splitting on it would
    manufacture a bogus ancestor language.

    Args:
        raw: A term, possibly annotated and/or lang-prefixed.
        default_lang: The language to use when `raw` carries no prefix.

    Returns:
        The ancestor's language code and its unannotated term.
    """
    stripped = _strip_inline_annotation(raw)
    if ":" in stripped:
        lang_code, _, term = stripped.partition(":")
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


def _affix_family_pieces(args: dict[str, str]) -> Iterator[str]:
    """Yield each present morpheme term of a same-language affix template.

    Positions start at args["2"]; "altN" (1-based per morpheme) overrides
    the Nth positional term when both are given. A missing or empty piece
    (a morpheme Wiktionary could not identify) is skipped.

    Args:
        args: The template's raw argument mapping.

    Yields:
        Each non-empty morpheme term, in order.
    """
    piece = 1
    while str(piece + 1) in args:
        raw = args.get(f"alt{piece}") or args.get(str(piece + 1), "")
        if raw:
            yield raw
        piece += 1


def _maybe_edge(
    src: Lexeme, dst: Lexeme, rel_type: RelType, source_ref: str
) -> Iterator[EtymEdge]:
    """Yield the edge, unless it would be a same-word self-loop.

    A template can name the entry's own headword -- Wiktionary uses this to
    cross-reference a different etymology section of the same word (e.g.
    {{der|pt|pt|matreira|pos=etymology 1}} on the entry for "matreira"
    itself), not to assert an ancestor. The natural key that decides row
    identity is (lang_code, headword, etymology_number); senses/pos are not
    part of it, so this can hold even when the two Lexeme objects aren't
    `==` equal.

    Args:
        src: The candidate ancestor lexeme.
        dst: The entry's own lexeme.
        rel_type: The relation type the template asserts.
        source_ref: Wiktionary page or template provenance.

    Yields:
        The edge, unless src and dst are the same word.
    """
    if (src.lang_code, src.headword, src.etymology_number) != (
        dst.lang_code,
        dst.headword,
        dst.etymology_number,
    ):
        yield EtymEdge(
            src=src, dst=dst, rel_type=rel_type, source_ref=source_ref
        )


def _edges_from_etymon(
    args: dict[str, str],
    entry_lang: str,
    context: _TemplateContext,
) -> Iterator[EtymEdge]:
    """Build the edge(s) a {{etymon}} (or {{ety}}) template describes.

    Args:
        args: The template's raw argument mapping.
        entry_lang: The entry's own Wiktionary language code.
        context: The descendant lexeme and provenance shared by every edge
            this template produces.

    Yields:
        One edge per ancestor the template asserts (two for an ":af"
        sub-relation's pair of morphemes, at most one otherwise). A second
        colon-prefixed value in args["4"] signals a chained relation
        (a further hop, not a second term) and is not followed here.
    """
    sub = args.get("2", "")
    if sub.startswith(":"):
        rel_code = _strip_inline_annotation(sub[1:])
        raw_terms = [args["3"]] if args.get("3") else []
        second = args.get("4", "")
        if rel_code == "af" and second and not second.startswith(":"):
            raw_terms.append(second)
    else:
        rel_code = "from"
        raw_terms = [sub] if sub else []

    rel_type = _ETYMON_SUB_REL_TYPES.get(rel_code)
    if rel_type is None or not raw_terms:
        return

    for raw_term in raw_terms:
        ancestor_lang, term = _lang_and_term(raw_term, entry_lang)
        if not term:
            continue
        src = _referenced_lexeme(ancestor_lang, term, context.dump_date)
        yield from _maybe_edge(src, context.dst, rel_type, context.source_ref)


def _edges_from_directional(
    args: dict[str, str],
    rel_type: RelType,
    dst: Lexeme,
    dump_date: str,
    source_ref: str,
) -> Iterator[EtymEdge]:
    """Build the edge(s) a directional template (e.g. {{inh}}) asserts.

    args["2"] is the ancestor's language, occasionally a comma-joined list
    (Wiktionary's convention for "the same term is a cognate borrowing shared
    by each language") rather than one language code.

    Args:
        args: The template's raw argument mapping.
        rel_type: The relation type the template asserts.
        dst: The entry's own lexeme.
        dump_date: The enwiktionary dump date, pinned into source_ref.
        source_ref: Wiktionary page or template provenance.

    Yields:
        One edge per language in args["2"].
    """
    ancestor_lang = args.get("2", "")
    term = args.get("4") or args.get("3", "")
    if not ancestor_lang or not term:
        return

    for lang in _split_lang_codes(ancestor_lang):
        src = _referenced_lexeme(lang, term, dump_date)
        yield from _maybe_edge(src, dst, rel_type, source_ref)


def _edges_from_entry(
    entry: Mapping[str, object], dump_date: str
) -> Iterator[EtymEdge]:
    """Extract edges from one entry's etymology templates.

    Args:
        entry: A parsed Wiktextract entry.
        dump_date: The dump date pinned into each lexeme's source_ref.

    Yields:
        The etymology edges the entry's templates produce.
    """
    dst = lexeme_of_entry(entry, dump_date)
    templates = cast(
        "list[Mapping[str, object]]", entry.get("etymology_templates", [])
    )
    for index, template in enumerate(templates):
        name = cast("str", template.get("name", ""))
        args = cast("dict[str, str]", template.get("args", {}))
        source_ref = f"{dst.source_ref}#etymology_templates:{index}:{name}"

        if name in {"etymon", "ety"}:
            context = _TemplateContext(dst, dump_date, source_ref)
            yield from _edges_from_etymon(args, dst.lang_code, context)
            continue

        if name in _AFFIX_FAMILY_TEMPLATES:
            lang_code = args.get("1", "")
            rel_type = TEMPLATE_REL_TYPES[name]
            if not lang_code:
                continue
            for raw_term in _affix_family_pieces(args):
                src = _referenced_lexeme(lang_code, raw_term, dump_date)
                yield from _maybe_edge(src, dst, rel_type, source_ref)
            continue

        if name in _MENTION_TEMPLATES:
            lang_code = args.get("1", "")
            raw_term = args.get("3") or args.get("2", "")
            if lang_code and raw_term:
                src = _referenced_lexeme(lang_code, raw_term, dump_date)
                yield from _maybe_edge(src, dst, RelType.MENTION, source_ref)
            continue

        if name not in _DIRECTIONAL_TEMPLATES:
            continue
        rel_type = TEMPLATE_REL_TYPES[name]
        yield from _edges_from_directional(
            args, rel_type, dst, dump_date, source_ref
        )
