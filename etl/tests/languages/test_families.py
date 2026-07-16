"""Tests for the language code -> family branch lookup."""

from __future__ import annotations

from etymyriad.languages import language_family


def test_language_family_known_code() -> None:
    """A code with a mapped branch resolves to its family name."""
    assert language_family("en") == "Germanic"


def test_language_family_unknown_code_returns_none() -> None:
    """An unmapped (non-IE) code returns None."""
    assert language_family("xx-nonexistent") is None


def test_language_family_pie_root_is_indo_european() -> None:
    """The PIE root code resolves to 'Indo-European', not a branch."""
    assert language_family("ine-pro") == "Indo-European"


def test_language_family_nrm_trusts_canonical_over_drift() -> None:
    """The "nrm" code resolves to Italic, its dump content's true family.

    Wiktionary's live module reassigned "nrm" to Narom, an unrelated
    Austronesian language, after retiring it as Norman's old Wikimedia-wiki
    code (now "nrf"). Our dump's "nrm" entries are genuinely Norman
    (Romance), the same drift pattern as the "bh"/"bho" case in name
    seeding.
    """
    assert language_family("nrm") == "Italic"
