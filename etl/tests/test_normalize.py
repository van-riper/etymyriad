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
    """A real {{inh}} template yields one ancestor -> entry edge.

    Real record: gem-pro "frijaz" ("free"), inherited from ine-pro *priHós
    ("beloved"). The sibling {{etymon}} template is not yet handled (cycle 2)
    and must not produce a second edge.
    """
    entry = {
        "word": "frijaz",
        "lang_code": "gem-pro",
        "pos": "adj",
        "senses": [{"glosses": ["free"]}],
        "etymology_templates": [
            {
                "name": "etymon",
                "args": {
                    "1": "gem-pro",
                    "id": "free",
                    "2": ":inh",
                    "3": "ine-pro:*priHós",
                },
            },
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
