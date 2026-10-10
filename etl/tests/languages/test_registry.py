"""Tests for linking a snapshot into languages and language sets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pytest

from etymyriad.languages._model import LanguageKind
from etymyriad.languages._registry import Registry, split_variety

if TYPE_CHECKING:
    from etymyriad.languages._snapshot import Snapshot


def _snapshot() -> Snapshot:
    return {
        "sources": {},
        "families": {
            "ine": {"name": "Indo-European"},
            "gem": {
                "name": "Germanic",
                "parent": "ine",
                "proto_language": "gem-pro",
            },
            "gmw": {"name": "West Germanic", "parent": "gem"},
            "itc": {"name": "Italic", "parent": "ine"},
        },
        "languages": {
            "en": {
                "name": "English",
                "type": "regular",
                "family": "gmw",
                "scripts": ["Latn", "Brai"],
                "iso639_1": "en",
                "iso639_3": "eng",
            },
            "gem-pro": {
                "name": "Proto-Germanic",
                "type": "reconstructed",
                "family": "gem",
            },
            "la": {"name": "Latin", "type": "regular", "family": "itc"},
            "xx": {"name": "Unclassified", "type": "regular"},
        },
        "varieties": {
            "la-cla": {"name": "Classical Latin", "parent": "la"},
            "la-vul": {"name": "Vulgar Latin", "parent": "la-cla"},
            "oc-pro": {"name": "Provençal", "parent": "la"},
            "roa-pro": {"name": "Proto-Romance", "parent": "la-vul"},
            "la-lat": {"name": "Late Latin", "parent": "la"},
            "en-US": {"name": "American English", "parent": "en"},
            "pt-BR": {"name": "Brazilian Portuguese", "parent": "la"},
            "cls": {"name": "Classical Sanskrit", "parent": "la"},
        },
    }


def test_set_path_and_hierarchy_run_root_first() -> None:
    """A set's hierarchy joins its lineage ISO 639-5 style."""
    gmw = Registry(_snapshot()).get_set("gmw")
    assert gmw is not None
    assert gmw.path == ("ine", "gem", "gmw")
    assert gmw.hierarchy == "ine:gem:gmw"


def test_language_points_at_its_set_object() -> None:
    """A language's set is the linked object, not a bare code."""
    registry = Registry(_snapshot())
    english = registry.get("en")
    assert english is not None
    assert english.language_set is registry.get_set("gmw")
    assert english.scripts == ("Latn", "Brai")
    assert english.iso639_3 == "eng"


def test_reconstructed_type_sets_kind_and_flag() -> None:
    """Wiktionary's own type marks a proto-language as reconstructed."""
    proto = Registry(_snapshot()).get("gem-pro")
    assert proto is not None
    assert proto.kind is LanguageKind.RECONSTRUCTED
    assert proto.is_reconstructed


def test_language_without_family_has_no_set() -> None:
    """Wiktionary leaves some languages unclassified."""
    unclassified = Registry(_snapshot()).get("xx")
    assert unclassified is not None
    assert unclassified.language_set is None


def test_variety_chain_reaches_full_language() -> None:
    """A variety of a variety still resolves to its full language."""
    registry = Registry(_snapshot())
    vulgar = registry.get("la-vul")
    assert vulgar is not None
    assert vulgar.kind is LanguageKind.VARIETY
    assert vulgar.full_language is registry.get("la")
    assert vulgar.language_set is registry.get_set("itc")


@pytest.mark.parametrize(
    ("code", "expected"),
    [("oc-pro", False), ("roa-pro", True), ("la-vul", False)],
    ids=["provencal-is-attested", "proto-romance", "plain-variety"],
)
def test_variety_reconstructed_needs_suffix_and_proto_name(
    code: str, *, expected: bool
) -> None:
    """A "-pro" variety counts as reconstructed only when named Proto-."""
    variety = Registry(_snapshot()).get(code)
    assert variety is not None
    assert variety.is_reconstructed is expected


def test_family_code_is_a_collective_language() -> None:
    """A family code used as a language resolves to its own set."""
    registry = Registry(_snapshot())
    germanic = registry.get("gem")
    assert germanic is not None
    assert germanic.kind is LanguageKind.COLLECTIVE
    assert germanic.name == "Germanic"
    assert germanic.language_set is registry.get_set("gem")


def test_family_cycle_raises() -> None:
    """A family that is its own ancestor fails loudly."""
    snapshot = _snapshot()
    snapshot["families"]["ine"]["parent"] = "gmw"
    with pytest.raises(ValueError, match="cycle"):
        Registry(snapshot)


@pytest.mark.parametrize(
    ("raw_code", "expected_code"),
    [
        ("en", "en"),
        ("LL.", "la-lat"),
        ("sa-cls", "cls"),
        ("en-us", "en-US"),
        ("pt-br", "pt-BR"),
    ],
    ids=["exact", "shorthand", "drift", "case", "second-case"],
)
def test_resolve_canonicalizes(raw_code: str, expected_code: str) -> None:
    """Shorthand, drift, and case variants all reach one canonical code."""
    language = Registry(_snapshot()).resolve(raw_code)
    assert language is not None
    assert language.code == expected_code


@pytest.mark.parametrize(
    "raw_code", ["ine-grp-pro", "g1", "", "EN", "EN-us", "LL"]
)
def test_resolve_unknown_returns_none(raw_code: str) -> None:
    """A code the snapshot never heard of resolves to nothing."""
    assert Registry(_snapshot()).resolve(raw_code) is None


@pytest.mark.parametrize(
    ("section", "code"),
    [("families", "en"), ("varieties", "EN")],
    ids=["family-reuses-language-code", "variety-differs-only-in-case"],
)
def test_colliding_codes_raise(
    section: Literal["families", "varieties"], code: str
) -> None:
    """Two records that would share one lookup key fail loudly."""
    snapshot = _snapshot()
    snapshot[section][code] = {"name": "Clash", "parent": "la"}
    with pytest.raises(ValueError, match="'en'"):
        Registry(snapshot)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("la-lat", ("la", "la-lat"), id="variety-under-full"),
        pytest.param("la", ("la", None), id="full-language-alone"),
        pytest.param(
            "zzz-notacode", ("zzz-notacode", None), id="unknown-unchanged"
        ),
    ],
)
def test_split_variety(code: str, expected: tuple[str, str | None]) -> None:
    """A variety files under its full language; other codes pass through."""
    assert split_variety(code) == expected
