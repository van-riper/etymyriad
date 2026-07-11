"""Tests for the Indo-European language filter."""

from __future__ import annotations

from etymyriad.languages import filter_indo_european, is_indo_european


def test_is_indo_european_true_for_known_language() -> None:
    """A known Indo-European language name matches."""
    assert is_indo_european({"lang": "Latin"}) is True


def test_is_indo_european_true_for_proto_indo_european() -> None:
    """The family root itself is recognized."""
    assert is_indo_european({"lang": "Proto-Indo-European"}) is True


def test_is_indo_european_false_for_unrelated_language() -> None:
    """A non-Indo-European language name does not match."""
    assert is_indo_european({"lang": "Japanese"}) is False


def test_is_indo_european_false_when_lang_missing() -> None:
    """An entry with no lang field never matches."""
    assert is_indo_european({}) is False


def test_filter_indo_european_keeps_only_matching_entries() -> None:
    """The stream filter drops non-Indo-European entries."""
    entries = [
        {"word": "water", "lang": "English"},
        {"word": "水", "lang": "Japanese"},
        {"word": "aqua", "lang": "Latin"},
    ]
    filtered = list(filter_indo_european(entries))
    assert [e["word"] for e in filtered] == ["water", "aqua"]
