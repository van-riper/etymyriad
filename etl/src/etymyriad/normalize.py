"""Map raw Wiktextract entries to graph objects.

Each Wiktextract entry describes one word and carries `etymology_templates`:
structured records of the {{inh}}, {{bor}}, {{der}}, ... templates used on the
page. We translate those into directed `EtymEdge`s (ancestor -> the entry's own
lexeme).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from etymyriad.model import EtymEdge, Lexeme, RelType

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


# A Wiktionary language code suffix marking a reconstructed proto-language
# (e.g. "gem-pro" for Proto-Germanic).
_PROTO_LANG_SUFFIX = "-pro"

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
# standalone template of their own, so they are not in TEMPLATE_REL_TYPES.
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
    raw_word = cast("str", entry.get("word", ""))
    headword, reconstructed = _strip_star(raw_word, lang_code)

    return Lexeme(
        lang_code=lang_code,
        headword=headword,
        gloss=_first_gloss(entry),
        pos=cast("str | None", entry.get("pos")),
        is_reconstructed=reconstructed,
        source_ref=f"wiktionary:{dump_date}:{lang_code}:{headword}",
    )


def _referenced_lexeme(lang_code: str, raw_term: str, dump_date: str) -> Lexeme:
    """Build the lexeme an etymology template points at (the ancestor side).

    Referenced lexemes carry no gloss: a template's inline gloss describes
    the sense relevant to that one etymology, not the ancestor's own
    canonical first sense, so recording it here would fragment the natural
    key away from the node built when the ancestor's own entry is parsed.

    Args:
        lang_code: The ancestor's Wiktionary language code.
        raw_term: The ancestor's term as written in the template, possibly
            starred.
        dump_date: The enwiktionary dump date, pinned into source_ref.

    Returns:
        The referenced lexeme.
    """
    headword, reconstructed = _strip_star(raw_term, lang_code)
    return Lexeme(
        lang_code=lang_code,
        headword=headword,
        is_reconstructed=reconstructed,
        source_ref=f"wiktionary:{dump_date}:{lang_code}:{headword}",
    )


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
    starred = raw.startswith("*")
    headword = raw[1:] if starred else raw
    return headword, starred or lang_code.endswith(_PROTO_LANG_SUFFIX)


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


def _lang_and_term(raw: str, default_lang: str) -> tuple[str, str]:
    """Split a term that may carry an explicit "lang:" prefix.

    Strips any trailing "<...>" annotation first, since annotations (e.g.
    "<id:away>") themselves contain colons that would otherwise be mistaken
    for the lang/term separator.

    Args:
        raw: A term, possibly annotated and/or lang-prefixed.
        default_lang: The language to use when `raw` carries no prefix.

    Returns:
        The ancestor's language code and its unannotated term.
    """
    stripped = _strip_inline_annotation(raw)
    if ":" in stripped:
        lang_code, _, term = stripped.partition(":")
        return lang_code, term
    return default_lang, stripped


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
        yield EtymEdge(
            src=src,
            dst=context.dst,
            rel_type=rel_type,
            source_ref=context.source_ref,
        )


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
                yield EtymEdge(
                    src=src, dst=dst, rel_type=rel_type, source_ref=source_ref
                )
            continue

        if name in _MENTION_TEMPLATES:
            lang_code = args.get("1", "")
            raw_term = args.get("3") or args.get("2", "")
            if lang_code and raw_term:
                src = _referenced_lexeme(lang_code, raw_term, dump_date)
                yield EtymEdge(
                    src=src,
                    dst=dst,
                    rel_type=RelType.MENTION,
                    source_ref=source_ref,
                )
            continue

        if name not in _DIRECTIONAL_TEMPLATES:
            continue
        rel_type = TEMPLATE_REL_TYPES[name]

        ancestor_lang = args.get("2", "")
        term = args.get("4") or args.get("3", "")
        if not ancestor_lang or not term:
            continue

        src = _referenced_lexeme(ancestor_lang, term, dump_date)
        yield EtymEdge(
            src=src, dst=dst, rel_type=rel_type, source_ref=source_ref
        )
