"""Tests for the language-family scope filter."""

from __future__ import annotations

import pytest

from etymyriad.languages import filter_in_scope, is_in_scope


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"lang_code": "la"}, True),
        ({"lang_code": "ine-pro"}, True),
        ({"lang_code": "sa-cls"}, True),
        ({"lang_code": "la-med"}, True),
        ({"lang_code": "lmo-old"}, True),
        ({"lang_code": "ja"}, False),
        ({"lang_code": "tdm"}, False),
        ({"lang_code": "ine-grp-pro"}, True),
        ({"lang_code": "xx-nonexistent"}, False),
        ({}, False),
    ],
    ids=[
        "known",
        "proto",
        "drifted",
        "variety",
        "nested-variety",
        "unrelated",
        "isolate",
        "unknown-ie-prefix",
        "unknown",
        "missing",
    ],
)
def test_is_in_scope(entry: dict[str, str], *, expected: bool) -> None:
    """Membership follows the root of the code's Wiktionary lineage."""
    assert is_in_scope(entry) is expected


@pytest.mark.parametrize(
    ("lang_code", "expected"),
    [("ar", True), ("sem-xyz", True), ("la", False)],
    ids=["known", "unknown-family-prefix", "out-of-scope"],
)
def test_scope_follows_scope_families(
    monkeypatch: pytest.MonkeyPatch, lang_code: str, *, expected: bool
) -> None:
    """A family added to SCOPE_FAMILIES brings its languages in."""
    monkeypatch.setattr(
        "etymyriad.languages._membership.SCOPE_FAMILIES", frozenset({"afa"})
    )
    assert is_in_scope({"lang_code": lang_code}) is expected


def test_filter_in_scope_keeps_only_matching_entries() -> None:
    """The stream filter drops entries outside the families in scope."""
    entries = [
        {"word": "etymology", "lang_code": "en"},
        {"word": "水", "lang_code": "ja"},
        {"word": "aqua", "lang_code": "la"},
    ]
    filtered = list(filter_in_scope(entries))
    assert [e["word"] for e in filtered] == ["etymology", "aqua"]
