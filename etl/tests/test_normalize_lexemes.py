"""Tests for the normalization layer's lexeme builders."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from etymyriad.normalize import lexeme_of_entry


def test_entry_missing_word_raises_validation_error() -> None:
    """A dump entry with no word fails loudly, not with a blank headword."""
    entry = {"lang_code": "en"}
    with pytest.raises(ValidationError):
        lexeme_of_entry(entry, dump_date="2026-06-01")


def test_entry_missing_lang_code_raises_validation_error() -> None:
    """A dump entry with no lang_code fails loudly, not with a blank one."""
    entry = {"word": "etymology"}
    with pytest.raises(ValidationError):
        lexeme_of_entry(entry, dump_date="2026-06-01")


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


def test_lexeme_of_entry_is_not_a_redlink() -> None:
    """A lexeme built from the entry's own page is never a redlink."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    lexeme = lexeme_of_entry(entry, dump_date="2026-06-01")
    assert lexeme.is_redlink is False
