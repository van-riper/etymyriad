"""Build `EtymEdge` objects from an entry's etymology templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge, Lexeme, RelType
from etymyriad.normalize._lexemes import _lexeme_of_parsed, _referenced_lexeme
from etymyriad.normalize._terms import (
    _AFFIX_HYPHEN_SIDE,
    _affix_base_piece,
    _affix_family_lang_and_offset,
    _affix_family_pieces,
    _affix_piece_count,
    _has_term,
    _lang_and_term,
    _split_lang_codes,
    _strip_inline_annotation,
)
from etymyriad.normalize._wiktextract import (
    _WiktextractEntry,
    _WiktextractSense,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

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
    "surf": RelType.SURFACE_ANALYSIS,
}


@dataclass(frozen=True, slots=True)
class _TemplateContext:
    """Provenance shared by every edge a single template call produces."""

    dst: Lexeme
    dump_date: str
    source_ref: str


# Directional templates: args["1"] is the entry's own language, args["2"] is
# the ancestor's language. The ancestor's term is args["4"] (an attested form)
# when present, else args["3"] (which may be a bound root). Wiktionary's own
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
# directional family's args["4"] overrides args["3"]. {{surf}} (surface
# analysis) shares this exact shape: editors write its own dashes too
# (e.g. "homo-"), so like {{affix}}/{{com}}/{{compound}} it needs no
# hyphen-side override below.
_AFFIX_FAMILY_TEMPLATES = frozenset({
    "af",
    "affix",
    "prefix",
    "suffix",
    "suf",
    "infix",
    "com",
    "compound",
    "surf",
})

# {{m}}/{{mention}}/{{m+}} cite a same-page mention rather than a structural
# derivation: args["1"] is the mentioned term's own language, args["2"] its
# term, with args["3"] (when present) overriding it the same way "altN"
# overrides a base term elsewhere.
_MENTION_TEMPLATES = frozenset({"m", "mention", "m+"})


def _maybe_edge(edge: EtymEdge) -> Iterator[EtymEdge]:
    """Yield the edge, unless it would be a same-word self-loop.

    A template can name the entry's own headword. Wiktionary uses this to
    cross-reference a different etymology section of the same word (e.g.
    {{der|pt|pt|matreira|pos=etymology 1}} on the entry for "matreira"
    itself), not to assert an ancestor. This can hold even when the two
    Lexeme objects aren't `==` equal.

    Args:
        edge: The candidate edge.

    Yields:
        edge, unless its src and dst are the same word.
    """
    if edge.src.natural_key != edge.dst.natural_key:
        yield edge


def _af_extra_terms(args: dict[str, str]) -> Iterator[str]:
    """Yield an ":af" etymon relation's morpheme terms past args["3"].

    Args:
        args: The template's raw argument mapping.

    Yields:
        Each present, non-empty term from args["4"] on, stopping at the
        first missing slot or the first colon-prefixed value (a chained
        relation, not a term).
    """
    arg_index = 4
    while str(arg_index) in args:
        term = args[str(arg_index)]
        if term.startswith(":"):
            return
        if _has_term(term):
            yield term
        arg_index += 1


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
        One edge per ancestor the template asserts (two or more for an
        ":af" sub-relation's morphemes, at most one otherwise). A
        colon-prefixed piece value signals a chained relation (a further
        hop, not a term) and ends the morpheme list there. An ":af"
        relation's edges carry a 1-based piece_order; a single-term
        relation is a whole-word derivation, not a composition piece, so
        it carries none.
    """
    sub = args.get("2", "")
    if sub.startswith(":"):
        rel_code = _strip_inline_annotation(sub[1:])
        raw_terms = [args["3"]] if _has_term(args.get("3", "")) else []
        if rel_code == "af":
            raw_terms.extend(_af_extra_terms(args))
    else:
        rel_code = "from"
        raw_terms = [sub] if _has_term(sub) else []

    rel_type = _ETYMON_SUB_REL_TYPES.get(rel_code)
    if rel_type is None or not raw_terms:
        return

    piece_count = len(raw_terms)
    for piece, raw_term in enumerate(raw_terms, start=1):
        ancestor_lang, term = _lang_and_term(raw_term, entry_lang)
        if not _has_term(term):
            continue
        src = _referenced_lexeme(ancestor_lang, term, context.dump_date)
        yield from _maybe_edge(
            EtymEdge(
                src=src,
                dst=context.dst,
                rel_type=rel_type,
                source_ref=context.source_ref,
                piece_order=piece if piece_count > 1 else None,
            )
        )


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
    if not ancestor_lang or not _has_term(term):
        return

    for lang in _split_lang_codes(ancestor_lang):
        src = _referenced_lexeme(lang, term, dump_date)
        yield from _maybe_edge(
            EtymEdge(src=src, dst=dst, rel_type=rel_type, source_ref=source_ref)
        )


def _edges_from_affix_family(
    name: str,
    args: dict[str, str],
    context: _TemplateContext,
) -> Iterator[EtymEdge]:
    """Build the edge(s) an affix-family template (e.g. {{suffix}}) asserts.

    Args:
        name: The template's name.
        args: The template's raw argument mapping.
        context: The descendant lexeme and provenance shared by every edge
            this template produces.

    Yields:
        One edge per morpheme piece the template names. A piece's own
        "lang:" prefix (see `_lang_and_term`) overrides the language
        shared by the rest of the template's pieces.
    """
    lang_code, offset = _affix_family_lang_and_offset(
        name, args, context.dst.lang_code
    )
    if not lang_code:
        return

    rel_type = TEMPLATE_REL_TYPES[name]
    side = _AFFIX_HYPHEN_SIDE.get(name)
    piece_count = _affix_piece_count(args, offset)
    base_piece = _affix_base_piece(name, piece_count)

    for piece, raw_term in _affix_family_pieces(args, offset):
        dash = side if piece != base_piece else None
        piece_lang, term = _lang_and_term(raw_term, lang_code)
        src = _referenced_lexeme(piece_lang, term, context.dump_date, dash)
        yield from _maybe_edge(
            EtymEdge(
                src=src,
                dst=context.dst,
                rel_type=rel_type,
                source_ref=context.source_ref,
                piece_order=piece,
            )
        )


def _edges_from_form_of(
    parsed: _WiktextractEntry, dst: Lexeme, dump_date: str
) -> Iterator[EtymEdge]:
    """Yield an inflection candidate for each form-of sense.

    Real record: la "adamantem" (accusative of "adamās") carries no
    etymology_templates at all; its only signal is a form-of sense.
    Candidates are filtered against the corpus-wide cited set by
    normalize(), not here; this yields unconditionally per sense.

    Args:
        parsed: The entry already validated by `_edges_from_entry`.
        dst: The entry's own lexeme (the form side).
        dump_date: The enwiktionary dump date, pinned into source_ref.

    Yields:
        One inflection edge per form-of sense naming a real headword
        (a multi-word form_of target, e.g. "diminutive suffix", is
        skipped as junk rather than a lemma).
    """
    for index, sense in enumerate(parsed.senses):
        if "form-of" not in sense.tags or not sense.form_of:
            continue
        term = sense.form_of[0].word
        if not _has_term(term) or any(char.isspace() for char in term):
            continue
        src = _referenced_lexeme(dst.lang_code, term, dump_date)
        source_ref = f"{dst.source_ref}#senses:{index}:form_of"
        yield from _maybe_edge(
            EtymEdge(
                src=src,
                dst=dst,
                rel_type=RelType.INFLECTION,
                source_ref=source_ref,
            )
        )


def _is_form_of_sense(sense: _WiktextractSense) -> bool:
    """True if a sense points at a lemma rather than describing one.

    Args:
        sense: One entry sense.

    Returns:
        True only when the sense is tagged form-of and names a target.
    """
    return "form-of" in sense.tags and bool(sense.form_of)


def _is_entirely_form_of(senses: list[_WiktextractSense]) -> bool:
    """True if a page has no sense of its own, only forms of another.

    Some non-lemma pages (e.g. en "book" etymology 3, "simple past of
    bake") carry etymology_templates copied from their lemma's own
    page, describing the lemma's ancestry rather than this form's. A
    page like this gets its ancestry from the inflection edge to its
    lemma instead, never from its own templates.

    Args:
        senses: The entry's senses.

    Returns:
        True only when senses is non-empty and every sense is form-of.
    """
    return bool(senses) and all(_is_form_of_sense(s) for s in senses)


def _is_entirely_form_of_entry(entry: Mapping[str, object]) -> bool:
    """True if the raw entry's own page has no sense but forms of another.

    Args:
        entry: A parsed Wiktextract entry.

    Returns:
        True only when every sense on the entry is form-of (see
        `_is_entirely_form_of`).
    """
    return _is_entirely_form_of(_WiktextractEntry.model_validate(entry).senses)


def _edges_from_entry(
    entry: Mapping[str, object], dump_date: str
) -> Iterator[EtymEdge]:
    """Extract edges from one entry's etymology templates.

    Args:
        entry: A parsed Wiktextract entry.
        dump_date: The dump date pinned into each lexeme's source_ref.

    Yields:
        The etymology edges the entry's templates produce, plus any
        inflection candidates its senses' form_of pointers describe.
        A page whose senses are entirely form-of yields no template
        edges, only the inflection edge(s) to its lemma.
    """
    parsed = _WiktextractEntry.model_validate(entry)
    dst = _lexeme_of_parsed(parsed, dump_date)
    if _is_entirely_form_of(parsed.senses):
        yield from _edges_from_form_of(parsed, dst, dump_date)
        return

    for index, template in enumerate(parsed.etymology_templates):
        name = template.name
        args = template.args
        source_ref = f"{dst.source_ref}#etymology_templates:{index}:{name}"

        if name in {"etymon", "ety"}:
            context = _TemplateContext(dst, dump_date, source_ref)
            yield from _edges_from_etymon(args, dst.lang_code, context)
            continue

        if name in _AFFIX_FAMILY_TEMPLATES:
            context = _TemplateContext(dst, dump_date, source_ref)
            yield from _edges_from_affix_family(name, args, context)
            continue

        if name in _MENTION_TEMPLATES:
            lang_code = args.get("1", "")
            raw_term = args.get("3") or args.get("2", "")
            if lang_code and _has_term(raw_term):
                src = _referenced_lexeme(lang_code, raw_term, dump_date)
                yield from _maybe_edge(
                    EtymEdge(
                        src=src,
                        dst=dst,
                        rel_type=RelType.MENTION,
                        source_ref=source_ref,
                    )
                )
            continue

        if name not in _DIRECTIONAL_TEMPLATES:
            continue
        rel_type = TEMPLATE_REL_TYPES[name]
        yield from _edges_from_directional(
            args, rel_type, dst, dump_date, source_ref
        )

    yield from _edges_from_form_of(parsed, dst, dump_date)
