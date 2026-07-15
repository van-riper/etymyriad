"""Tests for the language code -> name lookup."""

from __future__ import annotations

from etymyriad.language_names import language_name


def test_language_name_known_code() -> None:
    """A code seen in the dump resolves to its canonical name."""
    assert language_name("en") == "English"


def test_language_name_unknown_code_returns_none() -> None:
    """An unmapped code returns None, letting the caller fall back."""
    assert language_name("xx-nonexistent") is None


def test_language_name_bh_trusts_canonical_over_dump_majority() -> None:
    """The "bh" code resolves to "Bihari", the live module's assignment.

    The dump itself labels 429 "bh" entries "Bhojpuri" against a single
    "Bihari", but that majority is dump/extraction drift: Wiktionary's own
    Module:languages/data/2 still assigns "bh" to the Bihari macro-group,
    with "bho" as the separate, current code for Bhojpuri proper.
    """
    assert language_name("bh") == "Bihari"
