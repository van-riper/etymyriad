"""Tests for the normalization layer."""

from __future__ import annotations

from etymyriad.model import Lexeme, RelType
from etymyriad.normalize import (
    TEMPLATE_RELS,
    _edges_from_entry,
    lexeme_of_entry,
)


def test_template_map_covers_core_relations() -> None:
    """The template map resolves the core relation abbreviations."""
    assert TEMPLATE_RELS["inh"] is RelType.INHERITED
    assert TEMPLATE_RELS["bor"] is RelType.BORROWED
    assert TEMPLATE_RELS["der"] is RelType.DERIVED


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
    assert lexeme.gloss == "birch"


def test_gloss_absent_when_no_senses() -> None:
    """An entry with no glosses has a null gloss, not an empty string."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.gloss is None


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
    entry = {"word": "water", "lang_code": "en", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.is_reconstructed is False


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


def test_referenced_lexeme_carries_no_gloss() -> None:
    """An ancestor built from a template mention has no gloss.

    The template's gloss (e.g. "beloved") describes the sense relevant to
    this one etymology, not the ancestor's own canonical first sense. Setting
    it here would fragment the natural key away from the node built when the
    ancestor's own entry is parsed, so referenced lexemes stay glossless.
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

    assert edges[0].src.gloss is None


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
