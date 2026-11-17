"""Tests for the language-family scope filter."""

import pytest

from etymyriad.languages import is_in_scope


@pytest.mark.parametrize(
    ("lang_code", "expected"),
    [
        ("la", True),
        ("ine-pro", True),
        ("sa-cls", True),
        ("la-med", True),
        ("lmo-old", True),
        ("ja", False),
        ("tdm", False),
        ("ine-grp-pro", True),
        ("xx-nonexistent", False),
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
    ],
)
def test_is_in_scope(lang_code: str, *, expected: bool) -> None:
    """Membership follows the root of the code's Wiktionary lineage."""
    assert is_in_scope(lang_code) is expected


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
    assert is_in_scope(lang_code) is expected
