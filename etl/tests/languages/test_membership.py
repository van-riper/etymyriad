"""Tests for the Indo-European language filter."""

from __future__ import annotations

import pytest

from etymyriad.languages import filter_indo_european, is_indo_european


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"lang": "Latin"}, True),
        ({"lang": "Proto-Indo-European"}, True),
        ({"lang": "Japanese"}, False),
        ({}, False),
    ],
    ids=["known", "proto", "unrelated", "missing"],
)
def test_is_indo_european(entry: dict[str, str], *, expected: bool) -> None:
    """is_indo_european matches only known IE language names."""
    assert is_indo_european(entry) is expected


def test_filter_indo_european_keeps_only_matching_entries() -> None:
    """The stream filter drops non-Indo-European entries."""
    entries = [
        {"word": "etymology", "lang": "English"},
        {"word": "水", "lang": "Japanese"},
        {"word": "aqua", "lang": "Latin"},
    ]
    filtered = list(filter_indo_european(entries))
    assert [e["word"] for e in filtered] == ["etymology", "aqua"]
