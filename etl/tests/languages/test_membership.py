"""Tests for the dump filter's language check."""

import pytest

from etymyriad.languages import is_known_language


@pytest.mark.parametrize(
    ("lang_code", "expected"),
    [
        ("la", True),
        ("ine-pro", True),
        ("sa-cls", True),
        ("la-med", True),
        ("lmo-old", True),
        ("ja", True),
        ("ar", True),
        ("tdm", True),
        ("ine-grp-pro", True),
        ("sem-xyz", True),
        ("xx-nonexistent", False),
    ],
    ids=[
        "known",
        "proto",
        "drifted",
        "variety",
        "nested-variety",
        "japonic",
        "semitic",
        "isolate",
        "unknown-ie-prefix",
        "unknown-family-prefix",
        "unknown",
    ],
)
def test_is_known_language(lang_code: str, *, expected: bool) -> None:
    """Any code the registry resolves is kept, whatever its family."""
    assert is_known_language(lang_code) is expected
