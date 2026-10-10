"""Tests for joining Wiktionary exports with Wikidata ISO codes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.languages._snapshot import (
    WikidataIso,
    WiktionaryExports,
    build_snapshot,
)

if TYPE_CHECKING:
    from etymyriad.languages._snapshot import Snapshot

_WIKTIONARY = WiktionaryExports(
    languages={
        "en": {
            "1": "English",
            "2": 1860,
            "3": "gmw",
            "4": "Latn,Brai",
            "type": "regular",
            "wikimedia_codes": "en,simple",
        },
        "fr": {"1": "French", "2": 150, "3": "roa", "type": "regular"},
        "sh": {"1": "Serbo-Croatian", "2": 9301, "type": "regular"},
        "bh": {"1": "Bihari", "2": 135305, "type": "regular"},
        "pra": {"1": "Prakrit", "2": 192170, "type": "regular"},
        "ang": {"1": "Old English", "2": 42365, "type": "regular"},
        "mkh-mvi": {"1": "Middle Vietnamese", "2": 9199, "type": "regular"},
        "gmw-pro": {"1": "Proto-West Germanic", "type": "reconstructed"},
    },
    families={
        "gmw": {"1": "West Germanic", "2": 26721},
        "gmw-ang": {"1": "Anglic", "3": "gmw", "protoLanguage": "ang"},
        "cel-bry": {"1": "Brythonic"},
    },
    varieties={"la-lat": {"1": "Late Latin", "2": 1503113, "parent": "la"}},
)

_WIKIDATA = WikidataIso(
    iso639_3_by_item={
        1860: frozenset({"eng"}),
        150: frozenset({"fra"}),
        9301: frozenset({"hbs"}),
        42365: frozenset({"ang"}),
        9199: frozenset({"vie"}),
    },
    iso639_1_by_item={
        1860: frozenset({"en"}),
        150: frozenset({"fr"}),
        9301: frozenset({"sh"}),
        135305: frozenset({"bh"}),
    },
    iso639_2_by_item={150: frozenset({"fra", "fre"})},
    iso639_5_codes=frozenset({"gmw"}),
)


def _build() -> Snapshot:
    return build_snapshot(_WIKTIONARY, _WIKIDATA, {"wikidata": "CC0"})


def test_two_letter_code_joins_through_its_iso639_1_item() -> None:
    """Code "en" gets "eng" from the one item whose ISO 639-1 is "en"."""
    english = _build()["languages"]["en"]
    assert english.get("iso639_1") == "en"
    assert english.get("iso639_3") == "eng"


def test_deprecated_two_letter_code_keeps_only_iso639_1() -> None:
    """Code "sh" maps to "hbs"; "bh" has no ISO 639-3 code at all."""
    languages = _build()["languages"]
    assert languages["sh"].get("iso639_3") == "hbs"
    assert languages["bh"].get("iso639_1") == "bh"
    assert "iso639_3" not in languages["bh"]


def test_bibliographic_code_is_the_iso639_2_value_that_differs() -> None:
    """French's ISO 639-2/B code is "fre", not its 639-3 "fra"."""
    assert _build()["languages"]["fr"].get("iso639_2b") == "fre"


def test_three_letter_code_needs_wikidata_confirmation() -> None:
    """Code "ang" is confirmed; "pra" is an ISO collective, not 639-3."""
    languages = _build()["languages"]
    assert languages["ang"].get("iso639_3") == "ang"
    assert "iso639_3" not in languages["pra"]


def test_custom_code_never_borrows_its_qid_items_iso_code() -> None:
    """Joining by QID would wrongly give "mkh-mvi" the code "vie"."""
    assert "iso639_3" not in _build()["languages"]["mkh-mvi"]


def test_language_fields_are_unpacked() -> None:
    """Positional export fields become named, typed snapshot fields."""
    english = _build()["languages"]["en"]
    assert english["name"] == "English"
    assert english.get("family") == "gmw"
    assert english.get("wikidata_qid") == 1860
    assert english.get("scripts") == ["Latn", "Brai"]
    assert english.get("wikimedia_codes") == ["en", "simple"]


def test_family_proto_language_prefers_explicit_field() -> None:
    """Anglic names Old English; West Germanic falls back to "-pro"."""
    families = _build()["families"]
    assert families["gmw-ang"].get("proto_language") == "ang"
    assert families["gmw"].get("proto_language") == "gmw-pro"
    assert "proto_language" not in families["cel-bry"]


def test_family_iso639_5_needs_wikidata_confirmation() -> None:
    """Only codes Wikidata lists as ISO 639-5 carry the field."""
    families = _build()["families"]
    assert families["gmw"].get("iso639_5") == "gmw"
    assert "iso639_5" not in families["gmw-ang"]
    assert families["gmw-ang"].get("parent") == "gmw"


def test_variety_keeps_parent_and_sources_pass_through() -> None:
    """Varieties keep their parent; the attribution block is preserved."""
    snapshot = _build()
    assert snapshot["varieties"]["la-lat"] == {
        "name": "Late Latin",
        "parent": "la",
        "wikidata_qid": 1503113,
    }
    assert snapshot["sources"] == {"wikidata": "CC0"}


def test_self_parented_family_becomes_a_root() -> None:
    """Wiktionary marks its "not a family" root as its own parent."""
    wiktionary = WiktionaryExports(
        languages={},
        families={"qfa-not": {"1": "not a family", "3": "qfa-not"}},
        varieties={},
    )
    snapshot = build_snapshot(wiktionary, _WIKIDATA, {})
    assert "parent" not in snapshot["families"]["qfa-not"]
