"""Tests for the normalization layer."""

from __future__ import annotations

import pytest

from etymyriad.model import Lexeme, RelType
from etymyriad.normalize import (
    TEMPLATE_REL_TYPES,
    _edges_from_entry,
    lexeme_of_entry,
)


def test_template_map_covers_core_relations() -> None:
    """The template map resolves the core relation abbreviations."""
    assert TEMPLATE_REL_TYPES["inh"] is RelType.INHERITED
    assert TEMPLATE_REL_TYPES["bor"] is RelType.BORROWED
    assert TEMPLATE_REL_TYPES["der"] is RelType.DERIVED


def test_source_ref_carries_dump_date_and_lang_code() -> None:
    """source_ref pins the dump date and includes lang_code (homograph rule)."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.source_ref == "wiktionary:2026-06-01:gem-pro:berkō"


def test_gloss_read_from_first_sense() -> None:
    """The first sense's first gloss disambiguates homographs."""
    entry = {
        "word": "berkō",
        "lang_code": "gem-pro",
        "pos": "noun",
        "senses": [{"glosses": ["birch"]}, {"glosses": ["name of the rune"]}],
    }
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.senses[0].gloss == "birch"


def test_gloss_absent_when_no_senses() -> None:
    """An entry with no glosses has a null gloss, not an empty string."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.senses[0].gloss is None


def test_lexeme_carries_etymology_number_and_one_sense() -> None:
    """lexeme_of_entry reads etymology_number and builds one Sense.

    Real record: en "reverse" has four top-level entries. adj/adv/noun
    all carry etymology_number "1" (one shared derivation); the verb
    sense is a distinct etymology_number "2". Nodes must key on
    etymology_number, not gloss/pos, so those two live on a child Sense
    instead of on the lexeme itself.
    """
    entry = {
        "word": "reverse",
        "lang_code": "en",
        "pos": "adj",
        "etymology_number": "1",
        "senses": [{"glosses": ["Opposite, contrary."]}],
    }
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.etymology_number == "1"
    assert len(lexeme.senses) == 1
    assert lexeme.senses[0].pos == "adj"
    assert lexeme.senses[0].gloss == "Opposite, contrary."
    assert lexeme.senses[0].source_ref == lexeme.source_ref


def test_lexeme_etymology_number_absent_when_not_given() -> None:
    """An entry with no etymology_number field yields a null one."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.etymology_number is None


def test_reconstructed_headword_is_flagged() -> None:
    """A leading-asterisk headword is flagged as reconstructed."""
    entry = {"word": "*wréh₂ds", "lang_code": "ine-pro", "pos": "root"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.is_reconstructed is True
    assert lexeme.lang_code == "ine-pro"


def test_proto_own_entry_is_reconstructed_without_star() -> None:
    """Kaikki stores proto own-entries starless; the -pro code flags them."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.is_reconstructed is True
    assert lexeme.headword == "berkō"


def test_starred_headword_is_normalized() -> None:
    """A referenced proto form loses its leading star.

    This unifies it with the own-entry node so source_ref points at the
    real page, not a starred phantom.
    """
    entry = {"word": "*berkō", "lang_code": "gem-pro", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.headword == "berkō"
    assert lexeme.is_reconstructed is True
    assert lexeme.source_ref == "wiktionary:2026-06-01:gem-pro:berkō"


def test_plain_headword_is_not_reconstructed() -> None:
    """A plain headword is not flagged as reconstructed."""
    entry = {"word": "etymology", "lang_code": "en", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.is_reconstructed is False


def test_headword_strips_wiktextract_pua_markers() -> None:
    """Wiktextract's own link/nowiki placeholder chars never survive.

    Real record: de "Hackfleisch" appears in the raw dump with a pair of
    Supplementary Private Use Area-A markers (U+F003F, U+F0041) spliced
    into the word -- Wiktextract's own internal markup for a protected
    link/nowiki span mid-parse. They have no glyph by definition, so
    they must be stripped rather than stored.
    """
    entry = {
        "word": "Hack\U000f003ffleisch\U000f0041",
        "lang_code": "de",
        "pos": "noun",
    }
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.headword == "Hackfleisch"


def test_referenced_term_strips_wiktextract_pua_markers() -> None:
    """A template-cited ancestor term is cleaned the same way.

    Real record: it "idrogeno" cites an ancestor term written in the
    dump with the same pair of PUA-A markers spliced in.
    """
    entry = {
        "word": "idrogeno",
        "lang_code": "it",
        "pos": "noun",
        "etymology_templates": [
            {
                "name": "der",
                "args": {
                    "1": "it",
                    "2": "grc",
                    "3": "",
                    "4": "idr\U000f003fogeno\U000f0041",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].src.headword == "idrogeno"


def test_inh_template_yields_ancestor_to_entry_edge() -> None:
    """A real {{inh}} template yields an ancestor -> entry edge.

    Real record: gem-pro "frijaz" ("free"), inherited from ine-pro *priHós
    ("beloved"). The sibling {{etymon}} template documents the same relation
    independently and also yields an edge (see the etymon test below); both
    are harmless duplicates the loader's upsert coalesces.
    """
    entry = {
        "word": "frijaz",
        "lang_code": "gem-pro",
        "pos": "adj",
        "senses": [{"glosses": ["free"]}],
        "etymology_templates": [
            {
                "name": "inh",
                "args": {
                    "1": "gem-pro",
                    "2": "ine-pro",
                    "3": "*priHós",
                    "4": "",
                    "5": "beloved",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    edge = edges[0]
    assert edge.rel_type is RelType.INHERITED
    assert edge.src == Lexeme(
        lang_code="ine-pro",
        headword="priHós",
        is_reconstructed=True,
        source_ref="wiktionary:2026-06-01:ine-pro:priHós",
    )
    assert edge.dst.lang_code == "gem-pro"
    assert edge.dst.headword == "frijaz"
    assert edge.source_ref.startswith(
        "wiktionary:2026-06-01:gem-pro:frijaz#etymology_templates:"
    )


def test_der_and_root_on_one_entry_yield_two_distinct_edges() -> None:
    """{{der}} and {{root}} on one entry point at two different ancestors.

    Real record: gem-pro "an". {{der}} carries both a bound root (args["3"])
    and the specific attested form (args["4"]); Wiktionary's own expansion
    text displays args["4"] when present, so that is the term we take. The
    sibling {{root}} template has no args["4"] and falls back to args["3"],
    correctly pointing at a second, different ancestor lexeme.
    """
    entry = {
        "word": "an",
        "lang_code": "gem-pro",
        "pos": "prep",
        "etymology_templates": [
            {
                "name": "root",
                "args": {"1": "gem-pro", "2": "ine-pro", "3": "*h₂en-"},
            },
            {
                "name": "der",
                "args": {
                    "1": "gem-pro",
                    "2": "ine-pro",
                    "3": "*h₂en-",
                    "4": "*h₂én",
                    "5": "up, on high",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    by_rel = {edge.rel_type: edge for edge in edges}
    assert set(by_rel) == {RelType.ROOT, RelType.DERIVED}
    assert by_rel[RelType.ROOT].src.headword == "h₂en-"
    assert by_rel[RelType.DERIVED].src.headword == "h₂én"


def test_directional_comma_joined_lang_yields_one_edge_per_language() -> None:
    """A comma-joined ancestor language yields one edge per language.

    Real record: hrx "China", from {{bor+|hrx|pt-BR,de|China}} -- Wiktionary's
    convention for "this same spelling is a cognate borrowing shared by both
    languages", not a single language code. Left unsplit, this string would
    be upserted as a bogus `language.code` row instead of two real ones.
    """
    entry = {
        "word": "China",
        "lang_code": "hrx",
        "etymology_templates": [
            {
                "name": "bor+",
                "args": {"1": "hrx", "2": "pt-BR,de", "3": "China"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 2
    assert all(edge.rel_type is RelType.BORROWED for edge in edges)
    assert {edge.src.lang_code for edge in edges} == {"pt-BR", "de"}
    assert all(edge.src.headword == "China" for edge in edges)


def test_directional_strips_inline_id_annotation_from_term() -> None:
    """A directional template strips a trailing <id:...> annotation too.

    Wiktextract applies the same inline-annotation shape to the
    directional family's term argument as it does to {{etymon}}'s (see
    test_etymon_strips_inline_id_annotation_from_term); left unstripped,
    the annotated term leaks into the graph as its own node instead of
    merging with the real ancestor.
    """
    entry = {
        "word": "example",
        "lang_code": "en",
        "etymology_templates": [
            {
                "name": "der",
                "args": {
                    "1": "en",
                    "2": "la",
                    "3": "exemplum<id:sample>",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].src.headword == "exemplum"


@pytest.mark.parametrize(
    ("shorthand", "canonical"),
    [
        pytest.param("EL.", "la-ecc", id="EL.: Ecclesiastical Latin"),
        pytest.param("LL.", "la-lat", id="LL.: Late Latin"),
        pytest.param("ML.", "la-med", id="ML.: Medieval Latin"),
        pytest.param("NL.", "la-new", id="NL.: New Latin"),
        pytest.param("VL.", "la-vul", id="VL.: Vulgar Latin"),
    ],
)
def test_directional_latin_period_shorthand_resolves_to_canonical_code(
    shorthand: str, canonical: str
) -> None:
    """A directional template's Latin-period shorthand maps to its code.

    Real record: ca "reliquiarium", from {{bor|ca|EL.|reliquiarium}} --
    Wiktionary editors' own shorthand for Latin periods (Ecclesiastical,
    Late, Medieval, New, Vulgar Latin), used in place of the canonical
    Wiktextract code that appears everywhere else in the dataset for the
    same period. Left unmapped, each shorthand upserts as its own bogus
    `language.code` row instead of collapsing into the real one.
    """
    entry = {
        "word": "reliquiarium",
        "lang_code": "ca",
        "etymology_templates": [
            {
                "name": "bor",
                "args": {"1": "ca", "2": shorthand, "3": "reliquiarium"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].src.lang_code == canonical


def test_directional_literal_dash_term_yields_no_edge() -> None:
    """A literal "-" term asserts a relation with no specific term.

    Real record: cmn-pinyin entries write {{der|...|-}} to assert a
    language-level derivation without naming an attested term.
    Wiktextract passes the "-" straight through, so it must be treated
    the same as an absent argument -- otherwise every such template
    collapses onto one bogus "-" lexeme node per language.
    """
    entry = {
        "word": "example",
        "lang_code": "en",
        "etymology_templates": [
            {"name": "der", "args": {"1": "en", "2": "la", "3": "-"}},
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert edges == []


def test_referenced_lexeme_carries_no_senses() -> None:
    """An ancestor built from a template mention has no etymology_number.

    The template's gloss (e.g. "beloved") describes the sense relevant to
    this one etymology, not the ancestor's own canonical first sense. Setting
    it here would fragment the natural key away from the node built when the
    ancestor's own entry is parsed, so referenced lexemes carry no
    etymology_number and no senses.
    """
    entry = {
        "word": "frijaz",
        "lang_code": "gem-pro",
        "pos": "adj",
        "etymology_templates": [
            {
                "name": "inh",
                "args": {
                    "1": "gem-pro",
                    "2": "ine-pro",
                    "3": "*priHós",
                    "4": "",
                    "5": "beloved",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert edges[0].src.etymology_number is None
    assert edges[0].src.senses == ()


def test_same_language_affix_piece_carries_no_etymology_number() -> None:
    """A same-language bound-morpheme reference is not resolved here either.

    Real record: en "conjoin"'s {{af}} template names "con" as a piece,
    even though en "con" also has its own numbered dictionary entries
    elsewhere in the corpus -- a single entry's template gives no way
    to tell which numbered etymology it means, so `_referenced_lexeme`
    still leaves etymology_number unset here. Reconciling the resulting
    etym_key='' stub against a same-headword numbered sibling, when
    unambiguous, is `scripts/backfill_bound_morpheme_stubs.py`'s job
    (ETYM-96), not normalize.py's -- it runs after the whole corpus is
    loaded, since only then is it known whether "con" has exactly one
    numbered sibling.
    """
    entry = {
        "word": "conjoin",
        "lang_code": "en",
        "pos": "verb",
        "etymology_templates": [
            {
                "name": "af",
                "args": {"1": "en", "2": "con-", "3": "join"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    con_piece = next(e for e in edges if e.src.headword == "con-")
    assert con_piece.src.etymology_number is None
    assert con_piece.src.senses == ()


def test_etymon_inh_relation_matches_sibling_inh_template() -> None:
    """{{etymon}} with an ":inh" sub-relation yields an INHERITED edge.

    Real record: gem-pro "ab" ("away from, off of"), which carries both an
    {{etymon}} (sub-relation ":inh", term "ine-pro:*h₂epó<id:away>") and a
    plain {{inh}} template documenting the very same relation. Both fire and
    both point at the same ancestor.
    """
    entry = {
        "word": "ab",
        "lang_code": "gem-pro",
        "pos": "prep",
        "etymology_templates": [
            {
                "name": "etymon",
                "args": {
                    "1": "gem-pro",
                    "id": "away",
                    "2": ":inh",
                    "3": "ine-pro:*h₂epó<id:away>",
                },
            },
            {
                "name": "inh",
                "args": {"1": "gem-pro", "2": "ine-pro", "3": "*h₂epó"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 2
    assert all(edge.rel_type is RelType.INHERITED for edge in edges)
    assert all(edge.src.lang_code == "ine-pro" for edge in edges)
    assert all(edge.src.headword == "h₂epó" for edge in edges)


def test_etymon_bare_term_defaults_to_entry_language() -> None:
    """{{etymon}} with no sub-relation code is a bare same-language term.

    Real record: gem-pro "maist" ("most"), whose only etymology template is
    {{etymon|gem-pro|*maistaz}} -- no ":rel" in args["2"], so args["2"] is
    the term itself, in the entry's own language. Wiktionary's own expansion
    text calls this a "derived from" relation, so we take the generic
    DERIVED relation type (we cannot claim inherited/borrowed precision the
    template does not assert).
    """
    entry = {
        "word": "maist",
        "lang_code": "gem-pro",
        "pos": "adv",
        "etymology_templates": [
            {"name": "etymon", "args": {"1": "gem-pro", "2": "*maistaz"}},
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].rel_type is RelType.DERIVED
    assert edges[0].src.lang_code == "gem-pro"
    assert edges[0].src.headword == "maistaz"


def test_etymon_from_relation_with_explicit_lang_prefix() -> None:
    """{{etymon}}'s term can carry an explicit "lang:" prefix.

    Real record: gem-pro "upp" ("up, upwards"), whose only etymology
    template is {{etymon|gem-pro|:from|gem-pro:*ub}}: a same-language
    reference that still spells out its language code explicitly.
    """
    entry = {
        "word": "upp",
        "lang_code": "gem-pro",
        "pos": "adv",
        "etymology_templates": [
            {
                "name": "etymon",
                "args": {
                    "1": "gem-pro",
                    "id": "upwards",
                    "2": ":from",
                    "3": "gem-pro:*ub",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].rel_type is RelType.DERIVED
    assert edges[0].src.lang_code == "gem-pro"
    assert edges[0].src.headword == "ub"


def test_etymon_strips_inline_id_annotation_from_term() -> None:
    """{{etymon}} strips a trailing <id:...> annotation from the term.

    Real record: gem-pro "stelaną" ("to steal"), whose {{etymon}} template
    carries sub-relation ":root" and term "ine-pro:*tsel-<id:to sneak>".
    """
    entry = {
        "word": "stelaną",
        "lang_code": "gem-pro",
        "pos": "verb",
        "etymology_templates": [
            {
                "name": "etymon",
                "args": {
                    "1": "gem-pro",
                    "id": "to steal",
                    "2": ":root",
                    "3": "ine-pro:*tsel-<id:to sneak>",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].rel_type is RelType.ROOT
    assert edges[0].src.lang_code == "ine-pro"
    assert edges[0].src.headword == "tsel-"


def test_etymon_strips_uncertainty_annotation_from_relation_code() -> None:
    """{{etymon}} strips a trailing <unc> annotation from the relation code.

    Real record: gem-pro "beuną" ("to be, to become"), whose {{etymon}}
    template carries sub-relation ":der<unc>" -- the source flags the
    relation itself as uncertain, but still asserts it, so we still parse
    it as DERIVED.
    """
    entry = {
        "word": "beuną",
        "lang_code": "gem-pro",
        "pos": "verb",
        "etymology_templates": [
            {
                "name": "etymon",
                "args": {
                    "1": "gem-pro",
                    "2": ":der<unc>",
                    "3": "ine-pro:*bʰuHyéti",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].rel_type is RelType.DERIVED
    assert edges[0].src.lang_code == "ine-pro"
    assert edges[0].src.headword == "bʰuHyéti"


def test_etymon_af_term_with_embedded_colon_keeps_entry_language() -> None:
    """A term's own embedded colon is not mistaken for a "lang:" prefix.

    Real record: de "Forenbenutzer", from
    {{ety|de|:af|Forum (plural: Foren)|Benutzer}}. The first morpheme's
    parenthetical gloss contains a colon that is not a language prefix;
    splitting on it naively produces a bogus ancestor language
    ("Forum (plural") instead of the correct same-language ("de") morpheme.
    """
    entry = {
        "word": "Forenbenutzer",
        "lang_code": "de",
        "etymology_templates": [
            {
                "name": "ety",
                "args": {
                    "1": "de",
                    "2": ":af",
                    "3": "Forum (plural: Foren)",
                    "4": "Benutzer",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 2
    assert all(edge.src.lang_code == "de" for edge in edges)
    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"Forum (plural: Foren)", "Benutzer"}


def test_etymon_wiki_interlink_prefix_is_not_a_language_code() -> None:
    """A "w:" wiki-interlink prefix is not mistaken for a language code.

    Real record: en "Walker", from {{ety|en|:af|
    w:Walking Liberty half dollar<alt:Walk(ing Liberty)>|-er<id:relational>}}.
    "w:" cross-refers to an English Wikipedia article title, which is
    Wiktionary's own interlink convention. It's not a two-letter-minimum
    language code, so the whole annotated string stays the term, in the entry's
    own language.
    """
    entry = {
        "word": "Walker",
        "lang_code": "en",
        "etymology_templates": [
            {
                "name": "ety",
                "args": {
                    "1": "en",
                    "2": ":af",
                    "3": "w:Walking Liberty half dollar<alt:Walk(ing Liberty)>",
                    "4": "-er<id:relational>",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 2
    assert all(edge.src.lang_code == "en" for edge in edges)
    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"w:Walking Liberty half dollar", "-er"}


def test_etymon_literal_dash_term_yields_no_edge() -> None:
    """{{etymon}}'s bare-term shape treats a literal "-" as no term too."""
    entry = {
        "word": "example",
        "lang_code": "en",
        "etymology_templates": [
            {"name": "etymon", "args": {"1": "en", "2": ":der", "3": "-"}},
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert edges == []


def test_prefix_template_yields_one_edge_per_morpheme() -> None:
    """{{prefix}} is same-language: each morpheme is its own ancestor edge.

    Real record: gem-pro "bilībaną", from {{prefix|gem-pro|bi|lībaną}}.
    Unlike the directional family, args["1"] is shared by every morpheme,
    not a distinct ancestor language. The prefix piece ("bi") gets a
    trailing dash even though the raw arg omits one: Wiktextract's own
    "expansion" field for this record renders it "*bi- + *lībaną", since
    {{prefix}} implies the dash positionally.
    """
    entry = {
        "word": "bilībaną",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "prefix",
                "args": {
                    "1": "gem-pro",
                    "2": "*bi",
                    "3": "*lībaną",
                    "pos": "verb",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 2
    assert all(edge.rel_type is RelType.AFFIX for edge in edges)
    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"bi-", "lībaną"}
    piece_order_by_headword = {e.src.headword: e.piece_order for e in edges}
    assert piece_order_by_headword == {"bi-": 1, "lībaną": 2}


def test_directional_template_edge_carries_no_piece_order() -> None:
    """A directional template's single term is not a composition piece."""
    entry = {
        "word": "father",
        "lang_code": "en",
        "etymology_templates": [
            {"name": "inh", "args": {"1": "en", "2": "enm", "3": "fader"}},
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].piece_order is None


def test_suffix_template_prefers_alt_over_base_term() -> None:
    """{{suffix}} prefers "altN" (1-based per morpheme) over the base term.

    Real record: gem-pro "þar", from
    {{suffix|gem-pro|sa|alt1=þa-|r|t1=that|t2=locative suffix}}. Wiktionary's
    own expansion text displays "þa-", not the base "sa", matching the same
    alt-preference the directional family already applies. The second
    piece ("r") gets a leading dash even though the raw arg omits one:
    the real expansion renders it "*þa- (...) + *-r (...)", since
    {{suffix}} implies the dash positionally on every piece but the base.
    """
    entry = {
        "word": "þar",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "suffix",
                "args": {
                    "1": "gem-pro",
                    "2": "*sa",
                    "alt1": "*þa-",
                    "3": "*r",
                    "t1": "that",
                    "t2": "locative suffix",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"þa-", "-r"}


def test_affix_family_skips_a_missing_piece() -> None:
    """A missing morpheme (elided in the source) yields no edge for it.

    Real record: gem-pro "frumô", from {{suffix|gem-pro||umô|t2=superlative}}
    -- the first morpheme is unknown, so args["2"] is empty. The surviving
    piece ("umô") still occupies the second (suffix) position, so it still
    gets a leading dash: the real expansion renders it "+ *-umô (...)".
    """
    entry = {
        "word": "frumô",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "suffix",
                "args": {
                    "1": "gem-pro",
                    "2": "",
                    "3": "*umô",
                    "t2": "superlative",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].src.headword == "-umô"


def test_compound_template_yields_one_edge_per_morpheme() -> None:
    """{{com}}/{{compound}} share the affix family's same-language shape.

    Real record: gem-pro "þritehun", from
    {{com|gem-pro|þrīz|tehun|t1=three|t2=ten}}.
    """
    entry = {
        "word": "þritehun",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "com",
                "args": {
                    "1": "gem-pro",
                    "2": "*þrīz",
                    "3": "*tehun",
                    "t1": "three",
                    "t2": "ten",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 2
    assert all(edge.rel_type is RelType.COMPOUND for edge in edges)
    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"þrīz", "tehun"}


def test_suf_and_infix_gaps_are_filled() -> None:
    """{{suf}} and {{infix}} were unmapped spelling variants of the family.

    Real records: gem-pro "agraz" ({{suf|gem-pro|ahwō|-raz}}) and ine-pro
    "linékʷti" ({{infix|ine-pro|leykʷ-|-né-|t1=to leave|pos2=nasal infix}}).
    """
    suf_entry = {
        "word": "agraz",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "suf",
                "args": {"1": "gem-pro", "2": "*ahwō", "3": "*-raz"},
            },
        ],
    }
    infix_entry = {
        "word": "linékʷti",
        "lang_code": "ine-pro",
        "etymology_templates": [
            {
                "name": "infix",
                "args": {
                    "1": "ine-pro",
                    "2": "*leykʷ-",
                    "3": "*-né-",
                    "t1": "to leave",
                    "pos2": "nasal infix",
                },
            },
        ],
    }

    suf_edges = list(_edges_from_entry(suf_entry, dump_date="2026-06-01"))
    infix_edges = list(_edges_from_entry(infix_entry, dump_date="2026-06-01"))

    assert {e.src.headword for e in suf_edges} == {"ahwō", "-raz"}
    assert {e.src.headword for e in infix_edges} == {"leykʷ-", "-né-"}
    assert all(e.rel_type is RelType.AFFIX for e in suf_edges + infix_edges)


def test_suffix_template_adds_missing_dash() -> None:
    """{{suf}}/{{suffix}} imply a leading dash even when the arg omits it.

    Reported live: en "linguistic", from {{suf|en|linguist|ic}} -- the
    bare "ic" was leaking into the graph as its own node, distinct from
    the real "-ic" suffix entry, fragmenting thousands of English
    derivations across two lexemes for what is one suffix. Wiktextract's
    own expansion field for this exact record renders "linguist + -ic",
    confirming the dash even though the raw arg is bare.
    """
    entry = {
        "word": "linguistic",
        "lang_code": "en",
        "etymology_templates": [
            {
                "name": "suf",
                "args": {"1": "en", "2": "linguist", "3": "ic"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"linguist", "-ic"}


def test_prefix_template_chain_adds_missing_dash_except_on_base() -> None:
    """A multi-piece {{prefix}} dashes every piece but the last (the base).

    Real record: it "trinitrotoluene", from
    {{prefix|it|tri|nitro|toluene}}, expanding to "tri- + nitro- +
    toluene" -- the base ("toluene") stays bare, the two prefixes before
    it both gain a trailing dash.
    """
    entry = {
        "word": "trinitrotoluene",
        "lang_code": "it",
        "etymology_templates": [
            {
                "name": "prefix",
                "args": {"1": "it", "2": "tri", "3": "nitro", "4": "toluene"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"tri-", "nitro-", "toluene"}


def test_infix_template_adds_missing_leading_and_trailing_dash() -> None:
    """{{infix}} dashes both sides of a bare non-base piece.

    Real record: tl "sumulat", from {{infix|tl|sulat|um}}, expanding to
    "sulat + -um-" -- the infixed piece ("um") gains a dash on both
    sides even though the raw arg carries neither.
    """
    entry = {
        "word": "sumulat",
        "lang_code": "tl",
        "etymology_templates": [
            {
                "name": "infix",
                "args": {"1": "tl", "2": "sulat", "3": "um"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"sulat", "-um-"}


def test_affix_family_strips_inline_id_annotation_from_term() -> None:
    """{{affix}} strips a trailing <id:...> annotation from each morpheme.

    Reported live: en "unsoiling", from
    {{affix|en|un-<id:reversive>|soil|-ing<id:gerund noun>}} -- the
    un-stripped annotations were leaking into the graph as their own nodes
    ("un-<id:reversive>", "-ing<id:gerund noun>") instead of merging with
    the real "un-" and "-ing" nodes.
    """
    entry = {
        "word": "unsoiling",
        "lang_code": "en",
        "etymology_templates": [
            {
                "name": "affix",
                "args": {
                    "1": "en",
                    "2": "un-<id:reversive>",
                    "3": "soil",
                    "4": "-ing<id:gerund noun>",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 3
    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"un-", "soil", "-ing"}


def test_affix_family_skips_a_literal_dash_piece() -> None:
    """A literal "-" morpheme piece asserts no specific term, like a gap.

    Mirrors test_affix_family_skips_a_missing_piece, but for an editor-
    written "-" placeholder rather than a genuinely empty argument.
    """
    entry = {
        "word": "linguistic",
        "lang_code": "en",
        "etymology_templates": [
            {
                "name": "suf",
                "args": {"1": "en", "2": "linguist", "3": "-"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].src.headword == "linguist"


def test_etymon_af_relation_yields_one_edge_per_morpheme() -> None:
    """Etymon's ":af" sub-relation has two same-language morphemes, not one.

    Real record: gem-pro "laizijaną", from
    {{etymon|gem-pro|:af|lizaną|-janą<id:causative>}}. Unlike the other
    etymon sub-relations, ":af" carries a second term in args["4"].
    """
    entry = {
        "word": "laizijaną",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "etymon",
                "args": {
                    "1": "gem-pro",
                    "2": ":af",
                    "3": "*lizaną",
                    "4": "*-janą<id:causative>",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 2
    assert all(edge.rel_type is RelType.AFFIX for edge in edges)
    headwords = {edge.src.headword for edge in edges}
    assert headwords == {"lizaną", "-janą"}
    piece_order_by_headword = {e.src.headword: e.piece_order for e in edges}
    assert piece_order_by_headword == {"lizaną": 1, "-janą": 2}


def test_etymon_single_term_relation_carries_no_piece_order() -> None:
    """A single-term etymon relation is a whole-word derivation, not a piece.

    Unlike ":af"'s pair, every other etymon sub-relation (and the
    bare-term "from" shape) names one whole ancestor word -- there is
    no second piece to be ordered relative to.
    """
    entry = {
        "word": "example",
        "lang_code": "en",
        "etymology_templates": [
            {"name": "etymon", "args": {"1": "en", "2": ":der", "3": "term"}},
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].piece_order is None


def test_m_plus_prefers_alt_term_over_base() -> None:
    """{{m+}} is a mention in the ancestor's own language, args["1"].

    Real record: gem-pro "gudą", from {{m+|ine-pro|gʷʰutós|gʷʰutóm}}.
    Wiktionary's own expansion text displays the third positional arg
    ("gʷʰutóm") over the second, the same alt-preference the directional
    family applies.
    """
    entry = {
        "word": "gudą",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "m+",
                "args": {"1": "ine-pro", "2": "*gʷʰutós", "3": "*gʷʰutóm"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].rel_type is RelType.MENTION
    assert edges[0].src.lang_code == "ine-pro"
    assert edges[0].src.headword == "gʷʰutóm"


def test_mention_strips_inline_id_annotation_from_term() -> None:
    """{{m}}/{{mention}}/{{m+}} strip a trailing <id:...> annotation too."""
    entry = {
        "word": "gudą",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "m",
                "args": {"1": "ine-pro", "2": "*gʷʰutós<id:libation>"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].src.headword == "gʷʰutós"


def test_m_plus_falls_back_to_base_term() -> None:
    """{{m+}} with no third arg uses the base term in args["2"].

    Real record: gem-pro "juta", from {{m+|gem-pro|ta|t=to, towards}}.
    """
    entry = {
        "word": "juta",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {
                "name": "m+",
                "args": {"1": "gem-pro", "2": "*ta", "t": "to, towards"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 1
    assert edges[0].src.lang_code == "gem-pro"
    assert edges[0].src.headword == "ta"


def test_mention_literal_dash_term_yields_no_edge() -> None:
    """{{m}}/{{mention}}/{{m+}} treat a literal "-" term as no term too."""
    entry = {
        "word": "gudą",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {"name": "m", "args": {"1": "ine-pro", "2": "-"}},
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert edges == []


@pytest.mark.parametrize(
    ("word", "lang_code", "template_name", "template_args"),
    [
        pytest.param(
            "augô",
            "gem-pro",
            "m-g",
            {"1": "eye"},
            id="m-g: gem-pro 'augô' (bare gloss, no term)",
        ),
        pytest.param(
            "nu",
            "gem-pro",
            "cog",
            {"1": "lt", "2": "nù", "3": "", "4": "now, well now"},
            id="cog: gem-pro 'nu' (cognate, not ancestor)",
        ),
        pytest.param(
            "gaits",
            "gem-pro",
            "ncog",
            {"1": "sem-pro", "2": "*gady-"},
            id="ncog: gem-pro 'gaits' (non-cognate)",
        ),
        pytest.param(
            "nemaną",
            "gem-pro",
            "noncog",
            {"1": "ine-pro", "2": "*ḱóm"},
            id="noncog: gem-pro 'nemaną'",
        ),
        pytest.param(
            "gudą",
            "gem-pro",
            "unk",
            {"1": "gem-pro"},
            id="unk: gem-pro 'gudą' (unknown origin)",
        ),
        pytest.param(
            "swa",
            "gem-pro",
            "unc",
            {"1": "gem-pro"},
            id="unc: gem-pro 'swa' (uncertain origin)",
        ),
        pytest.param(
            "ammǭ",
            "gem-pro",
            "onom",
            {"1": "gem-pro", "nocap": "1"},
            id="onom: gem-pro 'ammǭ'",
        ),
        pytest.param(
            "hlahjaną",
            "gem-pro",
            "onomatopoeic",
            {"1": "gem-pro", "nocap": "1"},
            id="onomatopoeic: gem-pro 'hlahjaną'",
        ),
        pytest.param(
            "slahaną",
            "gem-pro",
            "onomatopoeia",
            {"1": "gem-pro", "nocap": "1"},
            id="onomatopoeia: gem-pro 'slahaną'",
        ),
    ],
)
def test_non_ancestor_templates_yield_no_edge(
    word: str,
    lang_code: str,
    template_name: str,
    template_args: dict[str, str],
) -> None:
    """Templates that assert no ancestor, or cite a non-ancestor, yield [].

    Covers {{m-g}} (bare gloss annotation, no term of its own),
    {{cog}}/{{ncog}}/{{noncog}} (cites a sibling cognate, not an
    ancestor), {{unk}}/{{unc}} (origin marked unknown or uncertain), and
    {{onom}}/{{onomatopoeic}}/{{onomatopoeia}} (sound-imitative origin,
    not a lexeme). None of these name an ancestor lexeme, so
    _edges_from_entry must yield nothing for each real record below.
    """
    entry = {
        "word": word,
        "lang_code": lang_code,
        "etymology_templates": [
            {"name": template_name, "args": template_args},
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert edges == []


def test_same_word_der_template_yields_no_self_loop_edge() -> None:
    """A {{der}} that names the entry's own word is not a real ancestor.

    Real record: pt "matreira" (noun) carries {{bor+|pt|kea|matrêra}} (a
    real ancestor, Kabuverdianu) alongside {{der|pt|pt|matreira|pos=etymology
    1}} -- Wiktionary's cross-reference to a different etymology section of
    the *same* headword, not an ancestor. Building the naive ancestor lexeme
    for the second template would equal the entry's own lexeme (same
    lang_code, headword, and etymology_number), which the schema's
    etymology_no_self_loop
    check rejects; the parser must skip it before it ever reaches an edge.
    """
    entry = {
        "word": "matreira",
        "lang_code": "pt",
        "pos": "noun",
        "etymology_templates": [
            {
                "name": "bor+",
                "args": {"1": "pt", "2": "kea", "3": "matrêra"},
            },
            {
                "name": "der",
                "args": {
                    "1": "pt",
                    "2": "pt",
                    "3": "matreira",
                    "pos": "etymology 1",
                },
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-07-06"))

    assert len(edges) == 1
    assert edges[0].src.lang_code == "kea"
    assert edges[0].src.headword == "matrêra"


def test_dercat_yields_no_edge_even_with_a_non_language_second_arg() -> None:
    """{{dercat}} is a derivation-category marker, never a directed edge.

    Real records: gem-pro "at" ({{dercat|gem-pro|ine-pro}}, a real language
    pair) and gem-pro "handuz" ({{dercat|gem-pro|qfa-sub}}, where args["2"]
    is a quality flag, not a language). Both must yield nothing regardless
    of what args["2"] holds.
    """
    entry = {
        "word": "at",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {"name": "dercat", "args": {"1": "gem-pro", "2": "ine-pro"}},
        ],
    }
    degenerate_entry = {
        "word": "handuz",
        "lang_code": "gem-pro",
        "etymology_templates": [
            {"name": "dercat", "args": {"1": "gem-pro", "2": "qfa-sub"}},
        ],
    }

    assert list(_edges_from_entry(entry, dump_date="2026-06-01")) == []
    assert (
        list(_edges_from_entry(degenerate_entry, dump_date="2026-06-01")) == []
    )


def test_surf_template_yields_one_edge_per_morpheme() -> None:
    """{{surf}} shares the affix family's same-language shape.

    Real record: en "homological", from
    {{der|en|grc|ὁμός}} + {{surf|en|homo-|logical}}. Before this, "surf"
    was unmapped, so only the {{der}} edge (to "ὁμός") ever surfaced --
    "logical" silently dropped, even though its piece already carries its
    own dash and needs none added.
    """
    entry = {
        "word": "homological",
        "lang_code": "en",
        "etymology_templates": [
            {
                "name": "der",
                "args": {
                    "1": "en",
                    "2": "grc",
                    "3": "ὁμός",
                    "4": "",
                    "5": "same",
                },
            },
            {
                "name": "surf",
                "args": {"1": "en", "2": "homo-", "3": "logical", "nocap": "1"},
            },
        ],
    }

    edges = list(_edges_from_entry(entry, dump_date="2026-06-01"))

    assert len(edges) == 3
    surf_edges = [e for e in edges if e.rel_type is RelType.SURFACE_ANALYSIS]
    assert {e.src.headword for e in surf_edges} == {"homo-", "logical"}
