"""Tests for the normalization layer's top-level orchestration."""

from __future__ import annotations

import logging

import pytest

from etymyriad.model import EtymEdge, RelType, SectionClaim, Term
from etymyriad.normalize import normalize
from etymyriad.normalize._edges import _IGNORED_TEMPLATES, _MAPPED_TEMPLATES


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

    edges = list(normalize(entries))

    assert len(edges) == 1
    edge = edges[0]
    assert isinstance(edge, EtymEdge)
    assert edge.dst.headword == "etymology"


def test_normalize_yields_lone_term_when_entry_has_no_edges() -> None:
    """A zero-edge entry still reaches the load step as its own term.

    An entry whose only template is {{unk}} (etymology unknown) names
    no ancestor term, so _edges_from_entry yields nothing for it. Before this
    fix, an entry that produced zero edges had no other path into
    Postgres and silently vanished; normalize() must fall
    back to the entry's own term so its senses still load.
    """
    entry = {
        "word": "con",
        "lang_code": "en",
        "etymology_number": "3",
        "pos": "noun",
        "senses": [{"glosses": ["A confidence trick."]}],
        "etymology_templates": [
            {"name": "unk", "args": {"1": "en"}},
        ],
    }

    items = list(normalize([entry]))

    assert len(items) == 1
    assert isinstance(items[0], Term)
    assert items[0].headword == "con"
    assert items[0].senses


def test_normalize_yields_the_claims_a_numbered_section_states() -> None:
    """Real record: enm "or" Etymology 1 lists en "or" as a descendant."""
    entry = {
        "word": "or",
        "lang_code": "enm",
        "etymology_number": "1",
        "pos": "conj",
        "descendants": [{"lang_code": "en", "word": "or"}],
    }

    claims = [i for i in normalize([entry]) if isinstance(i, SectionClaim)]

    assert claims == [
        SectionClaim(Term("enm", "or", section=1), listed=Term("en", "or"))
    ]


def test_malformed_descendants_cost_only_the_claims(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bad Descendants list keeps the entry's edges and is logged."""
    entry = {
        "word": "or",
        "lang_code": "enm",
        "etymology_number": "1",
        "descendants": "not a list",
        "etymology_templates": [
            {"name": "inh", "args": {"1": "enm", "2": "ang", "3": "ōr"}}
        ],
    }

    with caplog.at_level(logging.WARNING):
        items = list(normalize([entry]))

    assert [type(item) for item in items] == [EtymEdge]
    assert "malformed section claims" in caplog.text


def test_normalize_yields_inflection_edge_for_a_cited_form() -> None:
    """A form's lemma-edge survives when it's cited as an ancestor.

    Real record: la "adamantem" (accusative of "adamās") has no
    etymology_templates of its own, but la "adamantinus" cites it as
    an ancestor via {{der}}, which is what makes it cited.
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

    items = list(normalize([citing_entry, form_entry]))

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

    The entry still reaches load via the term_of_entry fallback.
    """
    form_entry = {
        "word": "adamantem",
        "lang_code": "la",
        "senses": [
            {"tags": ["form-of"], "form_of": [{"word": "adamās"}]},
        ],
    }

    items = list(normalize([form_entry]))

    assert not any(isinstance(item, EtymEdge) for item in items)
    assert len(items) == 1
    assert isinstance(items[0], Term)
    assert items[0].headword == "adamantem"


def test_form_of_page_merges_with_its_homograph_lemma() -> None:
    """A form-of page shares its homograph lemma's term key."""
    lemma = {
        "lang_code": "la",
        "word": "aquila",
        "pos": "noun",
        "senses": [{"glosses": ["eagle"]}],
    }
    form = {
        "lang_code": "la",
        "word": "aquila",
        "pos": "adj",
        "senses": [
            {
                "glosses": ["inflection of aquilus"],
                "tags": ["form-of"],
                "form_of": [{"word": "aquilus"}],
            }
        ],
    }
    out = list(normalize([lemma, form]))
    assert {item.key for item in out if isinstance(item, Term)} == {
        ("la", "aquila")
    }


def test_normalize_yields_solo_entirely_form_of_entry() -> None:
    """A homograph-free entirely-form-of entry yields its own term.

    Real record: la "adamantem" (accusative of "adamas") has no
    homograph sharing its headword, so it yields
    its own term even though it is entirely form-of.
    """
    entry = {
        "word": "adamantem",
        "lang_code": "la",
        "pos": "noun",
        "senses": [
            {
                "glosses": ["accusative singular of adamas"],
                "tags": ["form-of"],
                "form_of": [{"word": "adamas"}],
            }
        ],
    }

    items = list(normalize([entry]))

    terms = [item for item in items if isinstance(item, Term)]
    assert len(terms) == 1
    assert terms[0].key == ("la", "adamantem")


def test_normalize_mixed_entry_inflection_edge_keeps_its_own_key() -> None:
    """A mixed lemma+form-of entry's own inflection edge stays merged.

    it "avvertito" mixes a real adjective sense with a past-participle-
    of sense pointing at "avvertire". Its own inflection edge keeps the
    entry's own key as its dst.
    """
    entry = {
        "word": "avvertito",
        "lang_code": "it",
        "pos": "adj",
        "senses": [
            {"glosses": ["warned"]},
            {
                "glosses": ["past participle of avvertire"],
                "tags": ["form-of"],
                "form_of": [{"word": "avvertire"}],
            },
        ],
        "etymology_templates": [
            {
                "name": "der",
                "args": {"1": "it", "2": "la", "3": "", "4": "advertere"},
            },
        ],
    }
    citing_entry = {
        "word": "citante",
        "lang_code": "it",
        "etymology_templates": [
            {"name": "der", "args": {"1": "it", "2": "it", "3": "avvertito"}},
        ],
    }

    items = list(normalize([entry, citing_entry]))

    inflection_edges = [
        item
        for item in items
        if isinstance(item, EtymEdge) and item.rel_type is RelType.INFLECTION
    ]
    assert len(inflection_edges) == 1
    assert inflection_edges[0].dst.key == ("it", "avvertito")


def _entry_with(*templates: dict) -> dict:
    return {
        "word": "x",
        "lang_code": "en",
        "etymology_templates": list(templates),
    }


def test_normalize_logs_a_template_it_neither_maps_nor_ignores(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A new template shows up as a visible gap, not a silent drop."""
    entry = _entry_with({"name": "zz-new", "args": {"1": "en"}})

    with caplog.at_level(logging.INFO):
        list(normalize([entry, entry]))

    assert "zz-new (2)" in caplog.text


def test_normalize_does_not_log_an_ignored_template(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A cognate states no ancestry, so dropping it is deliberate."""
    entry = _entry_with({"name": "cog", "args": {"1": "de", "2": "Wein"}})

    with caplog.at_level(logging.INFO):
        list(normalize([entry]))

    assert "cog" not in caplog.text


def test_normalize_logs_an_unmapped_etymon_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An etymon code with no relation type shows up in the log."""
    entry = _entry_with({
        "name": "etymon",
        "args": {"1": "en", "2": ":zz-new", "3": "de:Braut"},
    })

    with caplog.at_level(logging.INFO):
        list(normalize([entry]))

    assert "etymon:zz-new (1)" in caplog.text


def test_ignored_templates_overlap_no_mapped_template() -> None:
    """A template is either mapped or ignored, never both."""
    assert not _MAPPED_TEMPLATES & _IGNORED_TEMPLATES


@pytest.mark.parametrize(
    "name",
    ["displaced", "metathesis", "rebracketing", "from", "nl", "ar-root"],
)
def test_template_with_no_ancestry_is_ignored(
    name: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A template that names no ancestor is dropped without a log line.

    Real record: en "number", {{displaced|enm|ȝetæl}} names the word this
    one replaced, not an ancestor.
    """
    entry = _entry_with({"name": name, "args": {"1": "enm", "2": "ȝetæl"}})

    with caplog.at_level(logging.INFO):
        list(normalize([entry]))

    assert name not in caplog.text
