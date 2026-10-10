"""Golden facts about the committed registry snapshot.

A failure after a re-sync means Wiktionary or Wikidata changed. Check
the live module before editing an expected value here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from etymyriad.languages import (
    SNAPSHOT_PATH,
    Language,
    LanguageKind,
    default_registry,
    get_language_set,
    indo_european_branch,
    resolve_language,
)
from etymyriad.languages._aliases import DRIFT_ALIASES

_INVENTORY = Path(__file__).with_name("fixtures") / "dump_language_codes.txt"
# Graeco-Phrygian was removed from Wiktionary after the dump; "g1" is a
# malformed template argument, not a language.
_KNOWN_UNRESOLVABLE = frozenset({"ine-grp-pro", "g1"})


def _resolved(code: str) -> Language:
    language = resolve_language(code)
    assert language is not None, code
    return language


def test_english_bridges_both_namespaces() -> None:
    """English carries its ISO codes and its full Wiktionary lineage."""
    english = _resolved("en")
    assert english.iso639_1 == "en"
    assert english.iso639_3 == "eng"
    assert english.language_set is not None
    assert english.language_set.hierarchy == (
        "ine:gem:gmw:gmw-nsg:gmw-afr:gmw-ang"
    )


@pytest.mark.parametrize(
    ("code", "iso639_3"),
    [("sh", "hbs"), ("no", "nor"), ("fa", "fas"), ("ang", "ang")],
)
def test_iso639_3_codes(code: str, iso639_3: str) -> None:
    """Macrolanguage and plain codes both join to ISO 639-3."""
    assert _resolved(code).iso639_3 == iso639_3


def test_french_bibliographic_code() -> None:
    """French's ISO 639-2/B code differs from its 639-3 code."""
    assert _resolved("fr").iso639_2b == "fre"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("gem-pro", True),
        ("xil", True),
        ("roa-pro", True),
        ("bat-pro", True),
        ("oc-pro", False),
        ("la", False),
    ],
    ids=[
        "proto-language",
        "reconstructed-without-suffix",
        "proto-variety-under-attested-parent",
        "proto-variety",
        "provencal",
        "attested",
    ],
)
def test_reconstructed_flag(code: str, *, expected: bool) -> None:
    """The flag follows Wiktionary's type, not the "-pro" suffix alone."""
    assert _resolved(code).is_reconstructed is expected


def test_proto_language_belongs_to_its_family() -> None:
    """Proto-Germanic is a member of Germanic, which points back at it."""
    proto = _resolved("gem-pro")
    assert proto.language_set is get_language_set("gem")
    germanic = get_language_set("gem")
    assert germanic is not None
    assert germanic.proto_language_code == "gem-pro"


def test_romance_proto_language_is_latin() -> None:
    """A family can name an attested language as its ancestor."""
    romance = get_language_set("roa")
    assert romance is not None
    assert romance.proto_language_code == "la"


def test_wiktionary_hierarchy_not_iso() -> None:
    """Baltic sits under Balto-Slavic, which ISO 639-5 lacks."""
    baltic = get_language_set("bat")
    assert baltic is not None
    assert baltic.path == ("ine", "ine-bsl", "bat")
    assert baltic.iso639_5 == "bat"
    balto_slavic = get_language_set("ine-bsl")
    assert balto_slavic is not None
    assert balto_slavic.iso639_5 is None


@pytest.mark.parametrize(
    ("raw_code", "code", "full_code"),
    [
        ("LL.", "la-lat", "la"),
        ("la-vul", "la-vul", "la"),
        ("en-us", "en-US", "en"),
        ("sa-cls", "cls", "sa"),
    ],
)
def test_resolution(raw_code: str, code: str, full_code: str) -> None:
    """Aliases, drift, case, and variety chains all land correctly."""
    language = _resolved(raw_code)
    assert language.code == code
    assert language.full_language.code == full_code


def test_family_code_resolves_as_collective() -> None:
    """{{der|en|gem}} names Germanic, never Proto-Germanic."""
    germanic = _resolved("gem")
    assert germanic.kind is LanguageKind.COLLECTIVE
    assert germanic.name == "Germanic"


@pytest.mark.parametrize(
    ("code", "branch"),
    [
        ("en", "Germanic"),
        ("ine-pro", "Indo-European"),
        ("nrf", "Italic"),
        ("grc", "Hellenic"),
        ("ja", None),
        ("tdm", None),
    ],
)
def test_indo_european_branch(code: str, branch: str | None) -> None:
    """The branch is the set directly under "ine", or None outside it."""
    assert indo_european_branch(_resolved(code)) == branch


def test_codes_are_unique_across_kinds_and_case() -> None:
    """No family shares a code with a language, even ignoring case."""
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    codes = [
        code
        for section in ("languages", "families", "varieties")
        for code in snapshot[section]
    ]
    assert len({code.casefold() for code in codes}) == len(codes)


def test_every_dump_code_resolves() -> None:
    """New drift fails here, before a reload stores unknown codes."""
    inventory = _INVENTORY.read_text(encoding="utf-8").split()
    unresolved = {code for code in inventory if resolve_language(code) is None}
    assert unresolved == _KNOWN_UNRESOLVABLE


def test_drift_aliases_only_cover_removed_codes() -> None:
    """A drift alias may not shadow a code the live data still defines.

    A reassigned code would mean different things in old and new dumps,
    so a re-sync that revives one needs a human to decide, not a silent
    alias.
    """
    registry = default_registry()
    shadowed = {code for code in DRIFT_ALIASES if registry.get(code)}
    assert shadowed == set()
