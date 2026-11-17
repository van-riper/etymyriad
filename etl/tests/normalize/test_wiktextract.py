"""Tests for decoding raw entries into the fields the normalizer reads."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import msgspec

from etymyriad.normalize import WiktextractEntry, field_paths

if TYPE_CHECKING:
    from collections.abc import Mapping


def _trimmed(raw: Mapping[str, object]) -> dict[str, object]:
    """Decode a raw entry into the Struct and encode it back out.

    Returns:
        The entry as `filter` would write it.
    """
    entry = msgspec.json.decode(json.dumps(raw), type=WiktextractEntry)
    return json.loads(msgspec.json.encode(entry))


def test_decoding_drops_undeclared_keys() -> None:
    """Top-level fields the Struct doesn't declare are dropped."""
    entry = {
        "word": "aqua",
        "lang_code": "la",
        "translations": [{"word": "water"}],
        "sounds": [{"ipa": "/a.kwa/"}],
    }
    assert _trimmed(entry) == {"word": "aqua", "lang_code": "la"}


def test_decoding_trims_nested_structs() -> None:
    """Senses, form_of, and templates keep only their declared keys."""
    entry = {
        "word": "wines",
        "lang_code": "en",
        "senses": [
            {
                "glosses": ["plural of wine"],
                "tags": ["form-of", "plural"],
                "form_of": [{"word": "wine", "extra": "x"}],
                "senseid": ["en:plural"],
                "examples": [{"text": "two wines"}],
            }
        ],
        "etymology_templates": [
            {
                "name": "inh",
                "args": {"1": "en", "2": "enm", "3": "wyn"},
                "expansion": "Middle English wyn",
            }
        ],
    }
    assert _trimmed(entry) == {
        "word": "wines",
        "lang_code": "en",
        "senses": [
            {
                "glosses": ["plural of wine"],
                "tags": ["form-of", "plural"],
                "form_of": [{"word": "wine"}],
                "senseid": ["en:plural"],
            }
        ],
        "etymology_templates": [
            {"name": "inh", "args": {"1": "en", "2": "enm", "3": "wyn"}}
        ],
    }


def test_decoding_trims_descendants_at_every_depth() -> None:
    """Nested descendants lists are trimmed at every depth."""
    entry = {
        "word": "aqua",
        "lang_code": "la",
        "descendants": [
            {
                "word": "acqua",
                "lang_code": "it",
                "tags": ["inherited"],
                "descendants": [
                    {"word": "acqua", "lang_code": "scn", "raw_tags": ["r"]}
                ],
            }
        ],
    }
    assert _trimmed(entry) == {
        "word": "aqua",
        "lang_code": "la",
        "descendants": [
            {
                "word": "acqua",
                "lang_code": "it",
                "descendants": [{"word": "acqua", "lang_code": "scn"}],
            }
        ],
    }


def test_field_paths_list_every_field_the_struct_reads() -> None:
    """The paths match what older code wrote, so its sidecars still pass."""
    assert field_paths() == {
        "derived",
        "derived.descendants",
        "derived.lang_code",
        "derived.word",
        "descendants",
        "descendants.descendants",
        "descendants.lang_code",
        "descendants.word",
        "etymology_number",
        "etymology_templates",
        "etymology_templates.args",
        "etymology_templates.name",
        "lang_code",
        "original_title",
        "pos",
        "senses",
        "senses.form_of",
        "senses.form_of.word",
        "senses.glosses",
        "senses.senseid",
        "senses.tags",
        "word",
    }
