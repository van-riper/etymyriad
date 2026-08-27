"""Map raw Wiktextract entries to graph objects.

Each Wiktextract entry describes one word and carries `etymology_templates`:
structured records of the {{inh}}, {{bor}}, {{der}}, ... templates used on the
page. We translate those into directed `EtymEdge`s (ancestor -> the entry's own
lexeme).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from etymyriad.model import (
    PROTO_LANG_SUFFIX,
    EtymEdge,
    Lexeme,
    RelType,
    Sense,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

_log = logging.getLogger(__name__)


class _WiktextractSense(BaseModel):
    """One raw entry's sense, as Wiktextract emits it."""

    model_config = ConfigDict(extra="ignore")

    glosses: list[str] | None = None


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
# directional family's args["4"] overrides args["3"]. {{surf}} (surface
# analysis) shares this exact shape -- editors write its own dashes too
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


def normalize(
    entries: Iterable[Mapping[str, object]],
    dump_date: str,
) -> Iterator[EtymEdge | Lexeme]:
    """Yield etymology edges for every entry in the stream.

    An entry with no recognized-ancestor template (e.g. clipping,
    unk/unc, cog/ncog/noncog, onom*) yields no edges from
    `_edges_from_entry`; its own lexeme+senses would otherwise never
    reach the load step, since the loader derives every row it upserts
    from edge endpoints. Falling back to the entry's own lexeme in that
    case is what keeps such an entry from silently vanishing.

    A malformed entry (missing lang_code or word) is logged and skipped
    rather than aborting the rest of a run that can take over an hour
    against the full dump -- the same tradeoff `parse.stream_entries`
    makes for a malformed JSONL line.

    Args:
        entries: Parsed Wiktextract entries.
        dump_date: The dump date pinned into each edge's provenance.

    Yields:
        The etymology edges the stream produces, and each entry's own
        lexeme when it produced none.
    """
    for entry in entries:
        try:
            edges = list(_edges_from_entry(entry, dump_date))
        except ValidationError as e:
            _log.warning("skipping malformed entry: %s", e)
            continue
        if edges:
            yield from edges
        else:
            yield lexeme_of_entry(entry, dump_date)


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
        gloss=_first_gloss(parsed),
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
        dash: "leading", "trailing", "both", or None -- a positionally-
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


def _first_gloss(parsed: _WiktextractEntry) -> str | None:
    """Return the first sense's first gloss, or None if there is none."""
    for sense in parsed.senses:
        if sense.glosses:
            return sense.glosses[0]
    return None


def _strip_inline_annotation(raw: str) -> str:
    """Drop a trailing "<...>" annotation, e.g. "<id:away>" or "<unc>".

    Returns:
        The text before the first "<", or the whole string if there is none.
    """
    return raw.split("<", 1)[0]


def _has_term(raw: str) -> bool:
    """Whether a raw term argument names an actual attested term.

    Wiktionary editors write a literal "-" to assert a relation/language
    without naming a specific term (e.g. {{der|en|la|-}}) -- Wiktextract
    passes it through unchanged, so it must be treated the same as an
    absent argument. Left unhandled, every such template collapses onto
    one bogus "-" lexeme node per language.

    Args:
        raw: A raw term argument.

    Returns:
        Whether `raw` names a real term.
    """
    return bool(raw) and raw != "-"


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
        offset: Extra positions to skip before args["2"] -- 1 for a
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
    morpheme Wiktionary could not identify) -- {{prefix}}'s dash
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
    shifts the language from args["1"] to args["2"] -- but a minority of
    "+type" flags are themselves language-specific formation labels
    written "+<lang>-<description>" (e.g. "+it-deverbal" for an Italian
    deverbal noun), which carry no separate language argument at all: the
    pieces that follow are already in the entry's own language.
    Wiktextract's own "expansion" field never names a different language
    for these, confirming the label doesn't shift anything -- args["2"]
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
    language bare in args["1"], with pieces from args["2"] on -- offset
    0. {{surf}} adds its optional leading "+type" flag (see
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
# such convention -- a piece may be a prefix, root, or suffix in any
# position, so editors must and do write the dash themselves -- and are
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


def _maybe_edge(edge: EtymEdge) -> Iterator[EtymEdge]:
    """Yield the edge, unless it would be a same-word self-loop.

    A template can name the entry's own headword -- Wiktionary uses this to
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
    parsed = _WiktextractEntry.model_validate(entry)
    dst = _lexeme_of_parsed(parsed, dump_date)
    for index, template in enumerate(parsed.etymology_templates):
        name = template.name
        args = template.args
        source_ref = f"{dst.source_ref}#etymology_templates:{index}:{name}"

        if name in {"etymon", "ety"}:
            context = _TemplateContext(dst, dump_date, source_ref)
            yield from _edges_from_etymon(args, dst.lang_code, context)
            continue

        if name in _AFFIX_FAMILY_TEMPLATES:
            lang_code, offset = _affix_family_lang_and_offset(
                name, args, dst.lang_code
            )
            rel_type = TEMPLATE_REL_TYPES[name]
            if not lang_code:
                continue
            side = _AFFIX_HYPHEN_SIDE.get(name)
            piece_count = _affix_piece_count(args, offset)
            base_piece = _affix_base_piece(name, piece_count)
            for piece, raw_term in _affix_family_pieces(args, offset):
                dash = side if piece != base_piece else None
                src = _referenced_lexeme(lang_code, raw_term, dump_date, dash)
                yield from _maybe_edge(
                    EtymEdge(
                        src=src,
                        dst=dst,
                        rel_type=rel_type,
                        source_ref=source_ref,
                        piece_order=piece,
                    )
                )
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
