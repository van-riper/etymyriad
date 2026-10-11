"""Tests for the normalization layer's term builders."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from etymyriad.model import Sense, Term
from etymyriad.normalize import term_of_entry
from etymyriad.normalize._nodes import _referenced_term
from etymyriad.normalize._wiktextract import _section_of


def test_entry_missing_word_raises_validation_error() -> None:
    """A dump entry with no word fails loudly, not with a blank headword."""
    entry = {"lang_code": "en"}
    with pytest.raises(ValidationError):
        term_of_entry(entry)


def test_entry_missing_lang_code_raises_validation_error() -> None:
    """A dump entry with no lang_code fails loudly, not with a blank one."""
    entry = {"word": "etymology"}
    with pytest.raises(ValidationError):
        term_of_entry(entry)


def test_gloss_read_from_first_sense() -> None:
    """The first sense's first gloss disambiguates homographs."""
    entry = {
        "word": "berkō",
        "lang_code": "gem-pro",
        "pos": "noun",
        "senses": [{"glosses": ["birch"]}, {"glosses": ["name of the rune"]}],
    }
    term = term_of_entry(entry)
    assert term.senses[0].gloss == "birch"


def test_gloss_absent_when_no_senses() -> None:
    """An entry with no glosses has a null gloss, not an empty string."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    term = term_of_entry(entry)
    assert term.senses[0].gloss is None


def test_term_carries_section_and_one_sense() -> None:
    """term_of_entry reads the section and builds one Sense.

    Real record: en "reverse" has four top-level entries. adj/adv/noun
    all carry etymology_number "1" (one shared derivation); the verb
    sense is a distinct etymology_number "2". Nodes must key on
    etymology_number, not gloss/pos, so those two live on a child Sense
    instead of on the term itself.
    """
    entry = {
        "word": "reverse",
        "lang_code": "en",
        "pos": "adj",
        "etymology_number": "1",
        "senses": [{"glosses": ["Opposite, contrary."]}],
    }
    term = term_of_entry(entry)
    assert term.section == 1
    assert len(term.senses) == 1
    assert term.senses[0].part_of_speech == "adj"
    assert term.senses[0].gloss == "Opposite, contrary."


def test_term_section_is_zero_when_not_given() -> None:
    """An entry with no etymology_number field is unnumbered."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    term = term_of_entry(entry)
    assert term.section == 0


def test_reconstructed_headword_is_flagged() -> None:
    """A leading-asterisk headword is flagged as reconstructed."""
    entry = {"word": "*wréh₂ds", "lang_code": "ine-pro", "pos": "root"}
    term = term_of_entry(entry)
    assert term.is_reconstructed is True
    assert term.lang_code == "ine-pro"


def test_proto_own_entry_is_reconstructed_without_star() -> None:
    """Kaikki stores proto own-entries starless; the -pro code flags them."""
    entry = {"word": "berkō", "lang_code": "gem-pro", "pos": "noun"}
    term = term_of_entry(entry)
    assert term.is_reconstructed is True
    assert term.headword == "berkō"


def test_starred_headword_is_normalized() -> None:
    """A referenced proto form loses its leading star.

    This unifies it with the own-entry node, not a starred phantom.
    """
    entry = {"word": "*berkō", "lang_code": "gem-pro", "pos": "noun"}
    term = term_of_entry(entry)
    assert term.headword == "berkō"
    assert term.is_reconstructed is True


def test_plain_headword_is_not_reconstructed() -> None:
    """A plain headword is not flagged as reconstructed."""
    entry = {"word": "etymology", "lang_code": "en", "pos": "noun"}
    term = term_of_entry(entry)
    assert term.is_reconstructed is False


def test_headword_strips_wiktextract_pua_markers() -> None:
    """Wiktextract's own link/nowiki placeholder chars never survive.

    Real record: de "Hackfleisch" appears in the raw dump with a pair of
    Supplementary Private Use Area-A markers (U+F003F, U+F0041) spliced
    into the word, Wiktextract's own internal markup for a protected
    link/nowiki span mid-parse. They have no glyph by definition, so
    they must be stripped rather than stored.
    """
    entry = {
        "word": "Hack\U000f003ffleisch\U000f0041",
        "lang_code": "de",
        "pos": "noun",
    }
    term = term_of_entry(entry)
    assert term.headword == "Hackfleisch"


def test_referenced_term_drops_whitespace_before_annotation() -> None:
    """A newline between a term and its "<...>" annotation is not stored.

    Real record: fa "هسته‌ای" cites its ancestor in an {{ety}} template
    as the term, a newline, then the "<t:nucleus>" annotation.
    """
    term = _referenced_term("fa", "هسته\n<t:nucleus>")
    assert term.headword == "هسته"


def test_referenced_provencal_is_not_reconstructed() -> None:
    """Provençal is "oc-pro", and that "-pro" is no proto marker."""
    term = _referenced_term("oc-pro", "aire")
    assert (term.lang_code, term.variety_code) == ("oc", "oc-pro")
    assert not term.is_reconstructed


@pytest.mark.parametrize(
    ("raw_lang_code", "expected"),
    [
        pytest.param(
            "en-us",
            ("en", "en-US"),
            id="lowercase-variety-takes-canonical-case",
        ),
        pytest.param(
            "sa-cls",
            ("sa", "cls"),
            id="drifted-code-takes-current-code",
        ),
        pytest.param(
            "LL.",
            ("la", "la-lat"),
            id="latin-period-shorthand-resolves",
        ),
    ],
)
def test_referenced_code_resolves_to_full_language_and_variety(
    raw_lang_code: str, expected: tuple[str, str]
) -> None:
    """A template's raw code files under its full language and variety."""
    term = _referenced_term(raw_lang_code, "foo")
    assert (term.lang_code, term.variety_code) == expected


def test_referenced_unknown_proto_code_passes_through() -> None:
    """An unknown "-pro" code survives unchanged and stays reconstructed."""
    term = _referenced_term("ine-grp-pro", "anḗr")
    assert term.lang_code == "ine-grp-pro"
    assert term.is_reconstructed


def test_entry_lang_code_is_canonicalized() -> None:
    """An entry's own code goes through the registry too."""
    entry = {"word": "खान्देशी", "lang_code": "khn", "pos": "noun"}
    assert term_of_entry(entry).lang_code == "ahr"


def test_reconstruction_namespace_entry_is_reconstructed() -> None:
    """A Reconstruction-namespace page is reconstructed, whatever the type.

    Wiktionary types Proto-West Germanic "regular", yet nearly all its
    pages are reconstructions.
    """
    entry = {
        "word": "frijaz",
        "lang_code": "gmw-pro",
        "original_title": "Reconstruction:Proto-West Germanic/frijaz",
    }
    assert term_of_entry(entry).is_reconstructed


def test_mainspace_entry_of_attested_proto_language_is_not() -> None:
    """Proto-Norse is attested in runes; its mainspace pages are real."""
    entry = {"word": "raven", "lang_code": "gmq-pro"}
    assert not term_of_entry(entry).is_reconstructed


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(None, 0, id="missing-is-unspecified"),
        pytest.param("2", 2, id="plain-number-counts"),
        pytest.param("2a", 0, id="trailing-letter-is-unspecified"),
        pytest.param("99999", 0, id="beyond-smallint-is-unspecified"),
        pytest.param("²", 0, id="superscript-digit-is-unspecified"),
    ],
)
def test_section_of(raw: str | None, expected: int) -> None:
    """Only plain numbers within SMALLINT range count as a section."""
    assert _section_of(raw) == expected


def test_entry_term_carries_its_section() -> None:
    """An entry term carries its etymology section and first sense."""
    entry = {
        "lang_code": "en",
        "word": "bank",
        "etymology_number": "2",
        "pos": "noun",
        "senses": [{"glosses": ["a slope"]}],
    }
    assert term_of_entry(entry) == Term(
        "en",
        "bank",
        section=2,
        senses=(Sense(part_of_speech="noun", gloss="a slope"),),
    )


def test_variety_reference_lands_on_the_full_language() -> None:
    """A variety reference files under its full language."""
    term = _referenced_term("la-lat", "*aquila")
    assert term == Term(
        "la", "aquila", is_reconstructed=True, variety_code="la-lat"
    )


def test_reconstructed_variety_reference_is_reconstructed() -> None:
    """A "-pro" variety reference is reconstructed under its full language."""
    term = _referenced_term("roa-pro", "cantare")
    assert (term.lang_code, term.variety_code) == ("la", "roa-pro")
    assert term.is_reconstructed
