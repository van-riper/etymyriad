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


def test_normalize_splits_entirely_form_of_dst_from_homograph_lemma() -> None:
    """An entirely-form-of dst gets its own row next to a homograph.

    Real record: la "aquila" is both a noun ("eagle") and, under the
    same headword, an entirely form-of adjective (ablative of
    "aquilus"). Merging them would graft the adjective's inflection
    onto the noun's node, so they must land as two distinct lexemes.
    """
    noun_entry = {
        "word": "aquila",
        "lang_code": "la",
        "pos": "noun",
        "senses": [{"glosses": ["eagle"]}],
    }
    adj_entry = {
        "word": "aquila",
        "lang_code": "la",
        "pos": "adj",
        "senses": [
            {
                "glosses": ["ablative feminine singular of aquilus"],
                "tags": ["form-of"],
                "form_of": [{"word": "aquilus"}],
            }
        ],
    }

    items = list(normalize([noun_entry, adj_entry], dump_date="2026-06-01"))

    lexemes = [item for item in items if isinstance(item, Lexeme)]
    by_pos = {lexeme.senses[0].pos: lexeme for lexeme in lexemes}
    assert set(by_pos) == {"noun", "adj"}
    assert by_pos["noun"].natural_key == ("la", "aquila", None)
    assert by_pos["adj"].natural_key != by_pos["noun"].natural_key


def test_normalize_splits_cited_inflection_edge_from_homograph_lemma() -> None:
    """A cited entirely-form-of dst's inflection edge also splits.

    Same la "aquila" shape as above, but this time "aquilus" is cited
    elsewhere as an ancestor, so the adjective's inflection edge
    survives the citation filter. Its dst must still land on the
    split identity, not the noun's.
    """
    noun_entry = {
        "word": "aquila",
        "lang_code": "la",
        "pos": "noun",
        "senses": [{"glosses": ["eagle"]}],
    }
    adj_entry = {
        "word": "aquila",
        "lang_code": "la",
        "pos": "adj",
        "senses": [
            {
                "glosses": ["ablative feminine singular of aquilus"],
                "tags": ["form-of"],
                "form_of": [{"word": "aquilus"}],
            }
        ],
    }
    citing_entry = {
        "word": "aquilifer",
        "lang_code": "la",
        "etymology_templates": [
            {"name": "der", "args": {"1": "la", "2": "la", "3": "aquila"}},
        ],
    }

    items = list(
        normalize([noun_entry, adj_entry, citing_entry], dump_date="2026-06-01")
    )

    inflection_edges = [
        item
        for item in items
        if isinstance(item, EtymEdge) and item.rel_type is RelType.INFLECTION
    ]
    assert len(inflection_edges) == 1
    edge = inflection_edges[0]
    assert edge.dst.headword == "aquila"
    assert edge.dst.natural_key != ("la", "aquila", None)


def test_normalize_keeps_solo_entirely_form_of_entry_unsplit() -> None:
    """A homograph-free entirely-form-of entry keeps its plain key.

    Real record: la "adamantem" (accusative of "adamas") has no
    homograph sharing its headword, so it merges exactly as before
    even though it is entirely form-of.
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

    items = list(normalize([entry], dump_date="2026-06-01"))

    lexemes = [item for item in items if isinstance(item, Lexeme)]
    assert len(lexemes) == 1
    assert lexemes[0].natural_key == ("la", "adamantem", None)


def test_normalize_mixed_entry_does_not_split_from_itself() -> None:
    """A mixed lemma+form-of entry's own inflection edge stays merged.

    it "avvertito" mixes a real adjective sense with a past-participle-
    of sense pointing at "avvertire". Its own natural key is trivially
    its own homograph sibling (itself), so the split must never
    trigger against a mixed entry's own key.
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

    items = list(normalize([entry, citing_entry], dump_date="2026-06-01"))

    inflection_edges = [
        item
        for item in items
        if isinstance(item, EtymEdge) and item.rel_type is RelType.INFLECTION
    ]
    assert len(inflection_edges) == 1
    assert inflection_edges[0].dst.natural_key == ("it", "avvertito", None)
