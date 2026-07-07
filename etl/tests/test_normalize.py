"""Tests for the normalization layer."""

from __future__ import annotations

from etymyriad.model import RelType
from etymyriad.normalize import TEMPLATE_RELS, lexeme_of_entry


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
