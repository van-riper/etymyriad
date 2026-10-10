"""Tests for the Indo-European language filter."""

from __future__ import annotations

import pytest

from etymyriad.languages import filter_indo_european, is_indo_european


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"lang_code": "la"}, True),
        ({"lang_code": "ine-pro"}, True),
        ({"lang_code": "sa-cls"}, True),
        ({"lang_code": "ja"}, False),
        ({"lang_code": "ine-grp-pro"}, True),
        ({"lang_code": "xx-nonexistent"}, False),
        ({}, False),
    ],
    ids=[
        "known",
        "proto",
        "drifted",
        "unrelated",
        "unknown-ie-prefix",
        "unknown",
        "missing",
    ],
)
def test_is_indo_european(entry: dict[str, str], *, expected: bool) -> None:
    """Membership follows the code's Wiktionary lineage."""
    assert is_indo_european(entry) is expected


def test_filter_indo_european_keeps_only_matching_entries() -> None:
    """The stream filter drops non-Indo-European entries."""
    entries = [
        {"word": "etymology", "lang_code": "en"},
        {"word": "水", "lang_code": "ja"},
        {"word": "aqua", "lang_code": "la"},
    ]
    filtered = list(filter_indo_european(entries))
    assert [e["word"] for e in filtered] == ["etymology", "aqua"]
