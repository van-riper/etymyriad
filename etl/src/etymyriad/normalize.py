"""Map raw Wiktextract entries to graph objects.

Each Wiktextract entry describes one word and carries `etymology_templates`:
structured records of the {{inh}}, {{bor}}, {{der}}, ... templates used on the
page. We translate those into directed `EtymEdge`s (ancestor -> the entry's own
lexeme).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge, Lexeme, RelType

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

# Wiktextract template name -> our relation type.
TEMPLATE_RELS: dict[str, RelType] = {
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
    "com": RelType.COMPOUND,
    "compound": RelType.COMPOUND,
    "cal": RelType.CALQUE,
    "calque": RelType.CALQUE,
    "cog": RelType.COGNATE,
    "cognate": RelType.COGNATE,
    "m": RelType.MENTION,
    "mention": RelType.MENTION,
}

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
# standalone template of their own, so they are not in TEMPLATE_RELS.
_ETYMON_SUB_RELS: dict[str, RelType] = {
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


def normalize(
    entries: Iterable[dict],
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


def lexeme_of_entry(entry: dict, dump_date: str) -> Lexeme:
    """Build the lexeme an entry describes (the descendant side).

    Args:
        entry: A parsed Wiktextract entry.
        dump_date: The enwiktionary dump date, pinned into source_ref.

    Returns:
        The lexeme the entry describes.
    """
    lang_code = entry.get("lang_code", "")
    headword, reconstructed = _strip_star(entry.get("word", ""), lang_code)

    return Lexeme(
        lang_code=lang_code,
        headword=headword,
        gloss=_first_gloss(entry),
        pos=entry.get("pos"),
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
    return headword, starred or lang_code.endswith("-pro")


def _first_gloss(entry: dict) -> str | None:
    """Return the first sense's first gloss, or None if there is none."""
    for sense in entry.get("senses", []):
        glosses = sense.get("glosses")
        if glosses:
            return glosses[0]
    return None


def _strip_inline_annotation(raw: str) -> str:
    """Drop a trailing "<...>" annotation, e.g. "<id:away>" or "<unc>".

    Returns:
        The text before the first "<", or the whole string if there is none.
    """
    return raw.split("<", 1)[0]


def _edge_from_etymon(
    args: dict,
    entry_lang: str,
    dst: Lexeme,
    dump_date: str,
    source_ref: str,
) -> EtymEdge | None:
    """Build the edge a {{etymon}} (or {{ety}}) template describes.

    Args:
        args: The template's raw argument mapping.
        entry_lang: The entry's own Wiktionary language code.
        dst: The entry's own lexeme (the descendant).
        dump_date: The dump date pinned into the ancestor's source_ref.
        source_ref: The citation for the edge this template produces.

    Returns:
        The edge, or None if the template does not assert one we recognize.
    """
    sub = args.get("2", "")
    if sub.startswith(":"):
        rel_code = _strip_inline_annotation(sub[1:])
        raw_term = args.get("3", "")
    else:
        rel_code = "from"
        raw_term = sub

    rel_type = _ETYMON_SUB_RELS.get(rel_code)
    if rel_type is None or not raw_term:
        return None

    stripped = _strip_inline_annotation(raw_term)
    if ":" in stripped:
        ancestor_lang, _, term = stripped.partition(":")
    else:
        ancestor_lang, term = entry_lang, stripped
    if not term:
        return None

    src = _referenced_lexeme(ancestor_lang, term, dump_date)
    return EtymEdge(src=src, dst=dst, rel_type=rel_type, source_ref=source_ref)


def _edges_from_entry(entry: dict, dump_date: str) -> Iterator[EtymEdge]:
    """Extract edges from one entry's etymology templates.

    Args:
        entry: A parsed Wiktextract entry.
        dump_date: The dump date pinned into each lexeme's source_ref.

    Yields:
        The etymology edges the entry's templates produce.
    """
    dst = lexeme_of_entry(entry, dump_date)
    for index, template in enumerate(entry.get("etymology_templates", [])):
        name = template.get("name", "")
        args = template.get("args", {})
        source_ref = f"{dst.source_ref}#etymology_templates:{index}:{name}"

        if name in {"etymon", "ety"}:
            edge = _edge_from_etymon(
                args, dst.lang_code, dst, dump_date, source_ref
            )
            if edge is not None:
                yield edge
            continue

        if name not in _DIRECTIONAL_TEMPLATES:
            continue
        rel_type = TEMPLATE_RELS[name]

        ancestor_lang = args.get("2", "")
        term = args.get("4") or args.get("3", "")
        if not ancestor_lang or not term:
            continue

        src = _referenced_lexeme(ancestor_lang, term, dump_date)
        yield EtymEdge(
            src=src, dst=dst, rel_type=rel_type, source_ref=source_ref
        )
