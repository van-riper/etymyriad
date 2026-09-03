"""Tests for the normalization layer's top-level orchestration."""

from __future__ import annotations

from etymyriad.model import EtymEdge, Lexeme, RelType
from etymyriad.normalize import normalize


def test_normalize_skips_malformed_entry_and_keeps_going() -> None:
    """One malformed entry in the stream doesn't abort the whole run."""
    entries = [
        {"lang_code": "en"},  # missing word: malformed
        {
            "word": "etymology",
            "lang_code": "en",
            "etymology_templates": [
                {
                    "name": "der",
                    "args": {"1": "en", "2": "la", "4": "etymologia"},
                }
            ],
        },
    ]

    edges = list(normalize(entries, dump_date="2026-06-01"))

    assert len(edges) == 1
    edge = edges[0]
    assert isinstance(edge, EtymEdge)
    assert edge.dst.headword == "etymology"


def test_normalize_yields_lone_lexeme_when_entry_has_no_edges() -> None:
    """A zero-edge entry still reaches the load step as its own lexeme.

    Real record: en "con" etymology 3 ("Clipping of confidence trick")
    carries only a {{clipping}} template, which names no ancestor
    lexeme, so _edges_from_entry yields nothing for it. Before this
    fix, an entry that produced zero edges had no other path into
    Postgres and silently vanished; normalize() must fall
    back to the entry's own lexeme so its senses still load.
    """
    entry = {
        "word": "con",
        "lang_code": "en",
        "etymology_number": "3",
        "pos": "noun",
        "senses": [{"glosses": ["A confidence trick."]}],
        "etymology_templates": [
            {"name": "clipping", "args": {"1": "en", "2": "confidence trick"}},
        ],
    }

    items = list(normalize([entry], dump_date="2026-06-01"))

    assert len(items) == 1
    assert isinstance(items[0], Lexeme)
    assert items[0].headword == "con"
    assert items[0].senses


def test_normalize_yields_inflection_edge_for_a_cited_form() -> None:
    """A form's lemma-edge survives when it's cited as an ancestor.

    Real record: la "adamantem" (accusative of "adamās") has no
    etymology_templates of its own, but la "adamantinus" cites it as
    an ancestor via {{der}} -- that's what makes it cited.
    """
    citing_entry = {
        "word": "adamantinus",
        "lang_code": "la",
        "etymology_templates": [
            {
                "name": "der",
                "args": {"1": "la", "2": "la", "3": "adamantem"},
            },
        ],
    }
    form_entry = {
        "word": "adamantem",
        "lang_code": "la",
        "senses": [
            {"tags": ["form-of"], "form_of": [{"word": "adamās"}]},
        ],
    }

    items = list(normalize([citing_entry, form_entry], dump_date="2026-06-01"))

    inflection_edges = [
        item
        for item in items
        if isinstance(item, EtymEdge) and item.rel_type is RelType.INFLECTION
    ]
    assert len(inflection_edges) == 1
    assert inflection_edges[0].src.headword == "adamās"
    assert inflection_edges[0].dst.headword == "adamantem"


def test_normalize_drops_inflection_edge_for_an_uncited_form() -> None:
    """An uncited form's candidate is dropped.

    The entry still reaches load via the lexeme_of_entry fallback.
    """
    form_entry = {
        "word": "adamantem",
        "lang_code": "la",
        "senses": [
            {"tags": ["form-of"], "form_of": [{"word": "adamās"}]},
        ],
    }

    items = list(normalize([form_entry], dump_date="2026-06-01"))

    assert not any(isinstance(item, EtymEdge) for item in items)
    assert len(items) == 1
    assert isinstance(items[0], Lexeme)
    assert items[0].headword == "adamantem"
