"""Tests for trimming raw entries to the fields the models declare."""

from __future__ import annotations

from etymyriad.normalize import field_paths, project_entry


def test_project_entry_drops_undeclared_keys() -> None:
    """Top-level fields no model declares are dropped."""
    entry = {
        "word": "aqua",
        "lang_code": "la",
        "translations": [{"word": "water"}],
        "sounds": [{"ipa": "/a.kwa/"}],
    }
    assert project_entry(entry) == {"word": "aqua", "lang_code": "la"}


def test_project_entry_trims_nested_models() -> None:
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
    assert project_entry(entry) == {
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


def test_project_entry_recurses_through_descendants() -> None:
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
    assert project_entry(entry) == {
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


def test_project_entry_passes_a_misshapen_field_through() -> None:
    """A declared field of the wrong shape is left for validation."""
    entry = {"word": "x", "lang_code": "en", "senses": "oops"}
    assert project_entry(entry) == entry


def test_field_paths_cut_recursion_at_the_first_repeat() -> None:
    """Paths reach every declared field and stop where a model repeats."""
    paths = field_paths()
    assert {
        "word",
        "senses.form_of.word",
        "senses.senseid",
        "etymology_templates.args",
        "descendants.descendants",
    } <= paths
    assert not any(
        path.startswith("etymology_templates.args.") for path in paths
    )
    assert not any(
        path.startswith("descendants.descendants.") for path in paths
    )
