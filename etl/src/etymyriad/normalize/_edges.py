"""Build `EtymEdge` objects from an entry's etymology templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from etymyriad.model import EtymEdge, RelType, Term
from etymyriad.normalize._inline import inline_relations
from etymyriad.normalize._nodes import _referenced_term, _term_of_parsed
from etymyriad.normalize._terms import (
    _AFFIX_HYPHEN_SIDE,
    _affix_base_piece,
    _affix_dash_convention,
    _affix_family_lang_and_offset,
    _affix_family_pieces,
    _affix_piece_count,
    _confix_dash,
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
    "m": RelType.MENTION,
    "mention": RelType.MENTION,
    "m+": RelType.MENTION,
    "surf": RelType.SURFACE_ANALYSIS,
    "uder": RelType.DERIVED,
    "der+": RelType.DERIVED,
    "der-lite": RelType.DERIVED,
    "inh-lite": RelType.INHERITED,
    "ubor": RelType.BORROWED,
    "obor": RelType.BORROWED,
    "learned borrowing": RelType.LEARNED_BORROWING,
    "clq": RelType.CALQUE,
    "pcal": RelType.CALQUE,
    "partial calque": RelType.CALQUE,
    "sl": RelType.SEMANTIC_LOAN,
    "semantic loan": RelType.SEMANTIC_LOAN,
    "translit": RelType.TRANSLITERATION,
    "transliteration": RelType.TRANSLITERATION,
    "blend": RelType.BLEND,
    "univerbation": RelType.UNIVERBATION,
    "confix": RelType.AFFIX,
    "abor": RelType.BORROWED,
    "unadapted borrowing": RelType.BORROWED,
    "psm": RelType.BORROWED,
    "pclq": RelType.CALQUE,
    "pseudo-loan": RelType.DERIVED,
    "sa-com": RelType.COMPOUND,
    "sa-af": RelType.AFFIX,
    "contraction": RelType.SHORTENING,
}


@dataclass(frozen=True, slots=True)
class _TemplateContext:
    """Citation shared by every edge a single template call produces."""

    dst: Term
    anchor: str


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
    "uder",
    "der+",
    "der-lite",
    "inh-lite",
    "ubor",
    "obor",
    "learned borrowing",
    "clq",
    "pcal",
    "partial calque",
    "sl",
    "semantic loan",
    "translit",
    "transliteration",
    "abor",
    "unadapted borrowing",
    "psm",
    "pclq",
    "pseudo-loan",
})

# {{etymon}} (and its older alias {{ety}}) encode their relations as a
# sequence of positional args: a ":code" (e.g. ":inh", ":der<unc>") applies
# to every term after it until the next ":code". Terms before any code are
# in the entry's own language and assert only a generic "derived from".
# Several codes are spelled-out forms or aliases of one relation.
_ETYMON_SUB_REL_TYPES: dict[str, RelType] = {
    "inh": RelType.INHERITED,
    "bor": RelType.BORROWED,
    "ubor": RelType.BORROWED,
    "obor": RelType.BORROWED,
    "lbor": RelType.LEARNED_BORROWING,
    "slbor": RelType.SEMI_LEARNED_BORROWING,
    "der": RelType.DERIVED,
    "derived": RelType.DERIVED,
    "from": RelType.DERIVED,
    "vrd": RelType.DERIVED,
    "uder": RelType.DERIVED,
    "deverbal": RelType.DERIVED,
    "denominal": RelType.DERIVED,
    "denom": RelType.DERIVED,
    "nom": RelType.DERIVED,
    "nominalization": RelType.DERIVED,
    "root": RelType.ROOT,
    "af": RelType.AFFIX,
    "affix": RelType.AFFIX,
    "sa-af": RelType.AFFIX,
    "vrd-af": RelType.AFFIX,
    "afeq": RelType.SURFACE_ANALYSIS,
    "calque": RelType.CALQUE,
    "cal": RelType.CALQUE,
    "clq": RelType.CALQUE,
    "pcal": RelType.CALQUE,
    "partial calque": RelType.CALQUE,
    "blend": RelType.BLEND,
    "univ": RelType.UNIVERBATION,
    "univerbation": RelType.UNIVERBATION,
    "clip": RelType.SHORTENING,
    "clipping": RelType.SHORTENING,
    "bf": RelType.SHORTENING,
    "back-formation": RelType.SHORTENING,
    "ellipsis": RelType.SHORTENING,
    "ellip": RelType.SHORTENING,
    "abbr": RelType.SHORTENING,
    "abbrev": RelType.SHORTENING,
    "abbreviation": RelType.SHORTENING,
    "acro": RelType.SHORTENING,
    "init": RelType.SHORTENING,
    "sylabbr": RelType.SHORTENING,
    "apheretic": RelType.SHORTENING,
    "redup": RelType.REDUPLICATION,
    "reduplication": RelType.REDUPLICATION,
    "metathesis": RelType.METATHESIS,
    "translit": RelType.TRANSLITERATION,
    "transliteration": RelType.TRANSLITERATION,
    "sl": RelType.SEMANTIC_LOAN,
    "semantic loan": RelType.SEMANTIC_LOAN,
    "influence": RelType.INFLUENCE,
    "psm": RelType.BORROWED,
}

# Relations whose several terms are ordered pieces of one word. Several
# terms under any other relation are alternative or joint sources.
_PIECEWISE_REL_TYPES = frozenset({
    RelType.AFFIX,
    RelType.BLEND,
    RelType.UNIVERBATION,
    RelType.SURFACE_ANALYSIS,
})

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
    "blend",
    "univerbation",
    "confix",
    "sa-com",
    "sa-af",
    "contraction",
})

# Templates that share another template's argument shape and dash
# convention. The anchor still names the template the page uses.
_TEMPLATE_NAME_ALIASES: dict[str, str] = {
    "pre": "prefix",
    "com+": "com",
    "compound+": "compound",
    "surface analysis": "surf",
    "univ": "univerbation",
    "back-form": "back-formation",
    "backform": "back-formation",
    "backformation": "back-formation",
    "clip": "clipping",
    "nom": "nominalization",
    "m-lite": "m",
    "con": "confix",
}

# {{m}}/{{mention}}/{{m+}} cite a same-page mention rather than a structural
# derivation: args["1"] is the mentioned term's own language, args["2"] its
# term, with args["3"] (when present) overriding it the same way "altN"
# overrides a base term elsewhere.
_MENTION_TEMPLATES = frozenset({"m", "mention", "m+"})

# Templates naming one source word: args["1"] is the source's language,
# args["2"] its term, e.g. {{clipping|en|ponder}} on "pond".
_SINGLE_SOURCE_TEMPLATES: dict[str, RelType] = {
    "clipping": RelType.SHORTENING,
    "back-formation": RelType.SHORTENING,
    "bf": RelType.SHORTENING,
    "ellipsis": RelType.SHORTENING,
    "abbrev": RelType.SHORTENING,
    "initialism": RelType.SHORTENING,
    "acronym": RelType.SHORTENING,
    "short for": RelType.SHORTENING,
    "deverbal": RelType.DERIVED,
    "nominalization": RelType.DERIVED,
    "denominal verb": RelType.DERIVED,
    "vrd": RelType.DERIVED,
    "apheretic form": RelType.SHORTENING,
    "sylabbr": RelType.SHORTENING,
    "clipcomp": RelType.SHORTENING,
    "reduplication": RelType.REDUPLICATION,
}


@dataclass(frozen=True, slots=True)
class _ImpliedLanguageTemplate:
    """A language-specific template whose source language is fixed.

    Attributes:
        lang_code: The source's language, implied by the template name.
        term_arg: The positional argument holding the source term.
        rel_type: The relation the template asserts.
    """

    lang_code: str
    term_arg: str
    rel_type: RelType


# e.g. {{sa-root|खन्}} names a Sanskrit root, and {{hi-derform|deverb|खेलना}}
# puts a derivation-type code before the Hindi source.
_IMPLIED_LANGUAGE_TEMPLATES: dict[str, _ImpliedLanguageTemplate] = {
    "sa-root": _ImpliedLanguageTemplate("sa", "1", RelType.ROOT),
    "it-deverbal": _ImpliedLanguageTemplate("it", "1", RelType.DERIVED),
    "hi-derform": _ImpliedLanguageTemplate("hi", "2", RelType.DERIVED),
}

_MAPPED_TEMPLATES = (
    {"etymon", "ety"}
    | _AFFIX_FAMILY_TEMPLATES
    | _DIRECTIONAL_TEMPLATES
    | _MENTION_TEMPLATES
    | set(_SINGLE_SOURCE_TEMPLATES)
    | set(_IMPLIED_LANGUAGE_TEMPLATES)
    | set(_TEMPLATE_NAME_ALIASES)
)

# Templates that state no ancestor -> descendant relation: cognates and
# doublets (siblings, not ancestors), unknown or imitative origins, the
# people a word is named after, and formatting or reference helpers.
_IGNORED_TEMPLATES = frozenset({
    "cog",
    "cognate",
    "ncog",
    "noncog",
    "doublet",
    "dbt",
    "piecewise doublet",
    "internationalism",
    "intnat",
    "unk",
    "unknown",
    "unc",
    "uncertain",
    "onomatopoeic",
    "onomatopoeia",
    "onom",
    "coin",
    "coinage",
    "coined",
    "named-after",
    "named-after/list",
    "yesno",
    "glossary",
    "m-g",
    "lit",
    "nonlemma",
    "non-lemma",
    "dercat",
    "etydate",
    "etymid",
    "lang",
    "lg",
    "langname",
    "ref",
    "R",
    "wp",
    "sup",
    "!",
    ",",
    "senseno",
    "sense",
    "taxfmt",
    "taxlink",
    "word",
    "col-top",
    "zh-l",
    "zh-m",
    "ja-r",
    "str left",
    "str index-lite/logic",
    "str_index-lite",
    "fa-xlit",
    "xlit",
    "inc-ext",
    "q",
    "qualifier",
    "gloss",
    "gl",
    "nb...",
    "interproject-box",
    "participle of",
    "circa2",
    "C.E.",
    "CE",
    "egy-h",
    "ic",
    "or else",
    "as-verb set",
    "as-verb-c",
    "hi-verb set",
    "mr-verb set",
    "ca-verb-obj",
    "es-verb-obj",
    "it-verb-obj",
    "gentrade",
    "lena",
    "vern",
    "pagename",
    "smallcaps",
    "commonscat",
    "angbr",
    "IPAfont",
    "wikidata lexeme",
    "PIE word",
    "displaced",
    "metathesis",
    "rebracketing",
    "from",
    "der-lite/lang",
    "nl",
    "s",
    "n-g",
    "defdate",
    "ltc-l",
    "ar-root",
})


def _maybe_edge(edge: EtymEdge) -> Iterator[EtymEdge]:
    """Yield the edge, unless both ends are the same term.

    A template can name its own page's headword to point at another
    etymology section of it (e.g. {{der|pt|pt|matreira|pos=etymology 1}}
    on "matreira"). Tree nodes are terms, so that edge would make a node
    its own parent.

    Args:
        edge: The candidate edge.

    Yields:
        edge, unless its src and dst are the same term.
    """
    if edge.src.key != edge.dst.key:
        yield edge


def _etymon_groups(args: Mapping[str, str]) -> list[tuple[str, list[str]]]:
    """Split an {{etymon}} call's positional args into relation groups.

    Args:
        args: The template's raw argument mapping.

    Returns:
        Each relation code with the raw terms that follow it, in order.
        Terms before any code fall under "from". A missing or "-" term
        is skipped.
    """
    groups: list[tuple[str, list[str]]] = []
    arg_index = 2
    while str(arg_index) in args:
        value = args[str(arg_index)]
        if value.startswith(":"):
            groups.append((_strip_inline_annotation(value[1:]), []))
        elif _has_term(value):
            if not groups:
                groups.append(("from", []))
            groups[-1][1].append(value)
        arg_index += 1
    return groups


def _edges_from_inline_chain(
    raw_term: str,
    default_lang: str,
    context: _TemplateContext,
) -> Iterator[EtymEdge]:
    """Build the edges an <ety:...> chain inside a term argument states.

    Args:
        raw_term: The term argument, possibly carrying inline chains.
        default_lang: The language of an unprefixed term.
        context: The descendant term and anchor of the template that
            holds the chain; the anchor cites every hop, since that
            page is the one that states them.

    Yields:
        One edge per hop whose keyword has a relation type, ancestor to
        descendant.
    """
    for relation in inline_relations(raw_term, default_lang):
        rel_type = _ETYMON_SUB_REL_TYPES.get(relation.keyword)
        if rel_type is None:
            continue
        is_piece = rel_type in _PIECEWISE_REL_TYPES
        yield from _maybe_edge(
            EtymEdge(
                src=_referenced_term(relation.src_lang, relation.src_term),
                dst=_referenced_term(relation.dst_lang, relation.dst_term),
                rel_type=rel_type,
                anchor=context.anchor,
                piece_order=relation.piece_order if is_piece else None,
            )
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
        context: The descendant term and anchor shared by every edge
            this template produces.

    Yields:
        One edge per term under each relation code that has a relation
        type, plus the edges any term's inline chain states. Several
        terms under a piecewise relation (e.g. ":af", ":blend") carry a
        1-based piece_order; a lone term, or one of several sources
        under any other relation, carries none.
    """
    for rel_code, raw_terms in _etymon_groups(args):
        rel_type = _ETYMON_SUB_REL_TYPES.get(rel_code)
        if rel_type is None:
            continue
        is_pieces = len(raw_terms) > 1 and rel_type in _PIECEWISE_REL_TYPES
        for piece, raw_term in enumerate(raw_terms, start=1):
            ancestor_lang, term = _lang_and_term(raw_term, entry_lang)
            if not _has_term(term):
                continue
            yield from _maybe_edge(
                EtymEdge(
                    src=_referenced_term(ancestor_lang, term),
                    dst=context.dst,
                    rel_type=rel_type,
                    anchor=context.anchor,
                    piece_order=piece if is_pieces else None,
                )
            )
            yield from _edges_from_inline_chain(raw_term, entry_lang, context)


def _edges_from_directional(
    args: dict[str, str],
    rel_type: RelType,
    dst: Term,
    anchor: str,
) -> Iterator[EtymEdge]:
    """Build the edge(s) a directional template (e.g. {{inh}}) asserts.

    args["2"] is the ancestor's language, occasionally a comma-joined list
    (Wiktionary's convention for "the same term is a cognate borrowing shared
    by each language") rather than one language code.

    Args:
        args: The template's raw argument mapping.
        rel_type: The relation type the template asserts.
        dst: The entry's own term.
        anchor: Where on the entry the template sits.

    Yields:
        One edge per language in args["2"].
    """
    ancestor_lang = args.get("2", "")
    term = args.get("4") or args.get("3", "")
    if not ancestor_lang or not _has_term(term):
        return

    for lang in _split_lang_codes(ancestor_lang):
        src = _referenced_term(lang, term)
        yield from _maybe_edge(
            EtymEdge(src=src, dst=dst, rel_type=rel_type, anchor=anchor)
        )


def _edges_from_single_source(
    args: dict[str, str],
    rel_type: RelType,
    dst: Term,
    anchor: str,
) -> Iterator[EtymEdge]:
    """Build the edges a single-source template (e.g. {{clipping}}) asserts.

    The source is args["2"], or args["3"] when args["2"] is left empty
    (e.g. {{nom|la||oblātus}}). A comma-separated source lists
    alternatives, e.g. {{clip|en|advertise,advertisement}}.

    Args:
        args: The template's raw argument mapping.
        rel_type: The relation type the template asserts.
        dst: The entry's own term.
        anchor: Where on the entry the template sits.

    Yields:
        One edge per named source, or none if it names no term.
    """
    lang_code = args.get("1", "")
    raw_terms = args.get("2") or args.get("3", "")
    if not lang_code:
        return
    for raw_term in raw_terms.split(","):
        term = raw_term.strip()
        if not _has_term(term):
            continue
        yield from _maybe_edge(
            EtymEdge(
                src=_referenced_term(lang_code, term),
                dst=dst,
                rel_type=rel_type,
                anchor=anchor,
            )
        )


def _edges_from_implied_language(
    implied: _ImpliedLanguageTemplate,
    args: dict[str, str],
    dst: Term,
    anchor: str,
) -> Iterator[EtymEdge]:
    """Build the edge a language-specific template (e.g. {{sa-root}}) asserts.

    Args:
        implied: The template's fixed language, term slot, and relation.
        args: The template's raw argument mapping.
        dst: The entry's own term.
        anchor: Where on the entry the template sits.

    Yields:
        One edge from the named source, or none if it names no term.
    """
    raw_term = args.get(implied.term_arg, "")
    if not _has_term(raw_term):
        return
    src = _referenced_term(implied.lang_code, raw_term)
    yield from _maybe_edge(
        EtymEdge(src=src, dst=dst, rel_type=implied.rel_type, anchor=anchor)
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
        context: The descendant term and anchor shared by every edge
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
    convention = _affix_dash_convention(name, args)
    side = _AFFIX_HYPHEN_SIDE.get(convention)
    piece_count = _affix_piece_count(args, offset)
    base_piece = _affix_base_piece(convention, piece_count)

    for piece, raw_term in _affix_family_pieces(args, offset):
        if convention == "confix":
            dash = _confix_dash(piece, piece_count)
        else:
            dash = side if piece != base_piece else None
        piece_lang, term = _lang_and_term(raw_term, lang_code)
        src = _referenced_term(piece_lang, term, dash)
        yield from _maybe_edge(
            EtymEdge(
                src=src,
                dst=context.dst,
                rel_type=rel_type,
                anchor=context.anchor,
                piece_order=piece,
            )
        )


def _edges_from_form_of(
    parsed: _WiktextractEntry, dst: Term
) -> Iterator[EtymEdge]:
    """Yield an inflection candidate for each form-of sense.

    Real record: la "adamantem" (accusative of "adamās") carries no
    etymology_templates at all; its only signal is a form-of sense.
    Candidates are filtered against the corpus-wide cited set by
    normalize(), not here; this yields unconditionally per sense.

    Args:
        parsed: The entry already validated by `_edges_from_entry`.
        dst: The entry's own term (the form side).

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
        src = _referenced_term(dst.lang_code, term)
        anchor = f"senses:{index}:form_of"
        yield from _maybe_edge(
            EtymEdge(
                src=src,
                dst=dst,
                rel_type=RelType.INFLECTION,
                anchor=anchor,
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


def _unmapped_relation_names(entry: Mapping[str, Any]) -> Iterator[str]:
    """Yield each template name or etymon code with no mapping or ignore.

    Args:
        entry: A raw Wiktextract entry.

    Yields:
        Each such template name, and each such {{etymon}} code as
        "etymon:<code>", once per use.
    """
    for template in entry.get("etymology_templates") or []:
        name = template["name"]
        if name not in {"etymon", "ety"}:
            if name not in _MAPPED_TEMPLATES | _IGNORED_TEMPLATES:
                yield name
            continue
        args = template["args"]
        codes = [code for code, _ in _etymon_groups(args)]
        for value in args.values():
            if "<ety:" in value:
                relations = inline_relations(value, entry["lang_code"])
                codes.extend(relation.keyword for relation in relations)
        for code in codes:
            if code not in _ETYMON_SUB_REL_TYPES:
                yield f"etymon:{code}"


def _edges_from_entry(entry: Mapping[str, object]) -> Iterator[EtymEdge]:
    """Extract edges from one entry's etymology templates.

    Args:
        entry: A parsed Wiktextract entry.

    Yields:
        The etymology edges the entry's templates produce, plus any
        inflection candidates its senses' form_of pointers describe.
        A page whose senses are entirely form-of yields no template
        edges, only the inflection edge(s) to its lemma.
    """
    parsed = _WiktextractEntry.model_validate(entry)
    dst = _term_of_parsed(parsed)
    if _is_entirely_form_of(parsed.senses):
        yield from _edges_from_form_of(parsed, dst)
        return

    for index, template in enumerate(parsed.etymology_templates):
        anchor = f"etymology_templates:{index}:{template.name}"
        name = _TEMPLATE_NAME_ALIASES.get(template.name, template.name)
        args = template.args

        if name in {"etymon", "ety"}:
            context = _TemplateContext(dst, anchor)
            yield from _edges_from_etymon(args, dst.lang_code, context)
            continue

        if name in _AFFIX_FAMILY_TEMPLATES:
            context = _TemplateContext(dst, anchor)
            yield from _edges_from_affix_family(name, args, context)
            continue

        if name in _MENTION_TEMPLATES:
            lang_code = args.get("1", "")
            raw_term = args.get("3") or args.get("2", "")
            if lang_code and _has_term(raw_term):
                src = _referenced_term(lang_code, raw_term)
                yield from _maybe_edge(
                    EtymEdge(
                        src=src,
                        dst=dst,
                        rel_type=RelType.MENTION,
                        anchor=anchor,
                    )
                )
            continue

        if name in _SINGLE_SOURCE_TEMPLATES:
            rel_type = _SINGLE_SOURCE_TEMPLATES[name]
            yield from _edges_from_single_source(args, rel_type, dst, anchor)
            continue

        if name in _IMPLIED_LANGUAGE_TEMPLATES:
            implied = _IMPLIED_LANGUAGE_TEMPLATES[name]
            yield from _edges_from_implied_language(implied, args, dst, anchor)
            continue

        if name not in _DIRECTIONAL_TEMPLATES:
            continue
        rel_type = TEMPLATE_REL_TYPES[name]
        yield from _edges_from_directional(args, rel_type, dst, anchor)

    yield from _edges_from_form_of(parsed, dst)
