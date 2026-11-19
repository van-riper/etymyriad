"""Tests for the normalization layer's top-level orchestration."""

import logging
from typing import TYPE_CHECKING

import msgspec
import pytest

from etymyriad.model import EtymEdge, RelType, SectionClaim, Term
from etymyriad.normalize import WiktextractEntry
from etymyriad.normalize import normalize as normalize_structs
from etymyriad.normalize._edges import _IGNORED_TEMPLATES, _MAPPED_TEMPLATES

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import GraphItem


def normalize(entries: Iterable[Mapping[str, object]]) -> Iterator[GraphItem]:
    """Decode dict entries, then normalize them.

    Returns:
        What normalize yields for the entries.
    """
    return normalize_structs(
        msgspec.convert(entry, WiktextractEntry) for entry in entries
    )


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


def test_normalize_drops_a_lone_soft_redirect_with_no_one_target() -> None:
    """A redirect page that can't fold would only load as a redlink."""
    entry = {
        "word": "kun",
        "lang_code": "nan-hbl",
        "pos": "soft-redirect",
        "redirects": ["君", "軍"],
        "senses": [{"tags": ["no-gloss"]}],
    }
    assert list(normalize([entry])) == []


def test_normalize_yields_a_lone_soft_redirect_to_one_target() -> None:
    """The loader needs the redirect term to fold it into its target."""
    entry = {
        "word": "暗い",
        "lang_code": "ja",
        "pos": "soft-redirect",
        "redirects": ["くらい"],
    }
    assert list(normalize([entry])) == [
        Term("ja", "暗い", redirect_headword="くらい")
    ]


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


def test_normalize_yields_inflection_edge_when_the_lemma_has_a_page() -> None:
    """A form links to its lemma even when nothing cites the form.

    Real records: la "signaturus" names "signō" in form_of, and the
    lemma's own page is the plain "signo". The edge keeps the form_of
    spelling; the loader aliases it onto the page.
    """
    lemma_entry = {
        "word": "signo",
        "lang_code": "la",
        "senses": [{"glosses": ["to mark, sign"]}],
    }
    form_entry = {
        "word": "signaturus",
        "lang_code": "la",
        "senses": [
            {"tags": ["form-of"], "form_of": [{"word": "signō"}]},
        ],
    }

    items = list(normalize([form_entry, lemma_entry]))

    inflection_keys = [
        (item.src.key, item.dst.key)
        for item in items
        if isinstance(item, EtymEdge) and item.rel_type is RelType.INFLECTION
    ]
    assert inflection_keys == [(("la", "signō"), ("la", "signaturus"))]


def _inflection_keys(
    items: Iterable[GraphItem],
) -> list[tuple[tuple[str, str], tuple[str, str]]]:
    return [
        (item.src.key, item.dst.key)
        for item in items
        if isinstance(item, EtymEdge) and item.rel_type is RelType.INFLECTION
    ]


def test_stress_marked_lemma_links_to_its_page_title() -> None:
    """Real records: bg "пече" names "пека́", whose page is "пека"."""
    lemma_entry = {
        "word": "пека",
        "lang_code": "bg",
        "senses": [{"glosses": ["to bake"]}],
    }
    form_entry = {
        "word": "пече",
        "lang_code": "bg",
        "senses": [
            {"tags": ["form-of"], "form_of": [{"word": "пека́"}]},
        ],
    }

    items = list(normalize([form_entry, lemma_entry]))

    assert _inflection_keys(items) == [(("bg", "пека"), ("bg", "пече"))]


def test_lemma_with_a_page_as_cited_keeps_its_marks() -> None:
    """Real records: nn "alleen" names "allé", a page beside "alle"."""
    entries = [
        {"word": word, "lang_code": "nn", "senses": [{"glosses": [gloss]}]}
        for word, gloss in (("allé", "avenue"), ("alle", "avenue"))
    ]
    form_entry = {
        "word": "alleen",
        "lang_code": "nn",
        "senses": [
            {"tags": ["form-of"], "form_of": [{"word": "allé"}]},
        ],
    }

    items = list(normalize([form_entry, *entries]))

    assert _inflection_keys(items) == [(("nn", "allé"), ("nn", "alleen"))]


@pytest.mark.parametrize(
    ("lang_code", "form", "cited", "page"),
    [
        ("uk", "реформування", "реформува́ти impf or pf", "реформувати"),
        ("cs", "stal", "stát pf", "stát"),
        ("sv", "labben", "labb n", "labb"),
        ("uk", "духу", "дух m inan", "дух"),
    ],
)
def test_lemma_cited_with_a_gender_label_links_to_its_page(
    lang_code: str, form: str, cited: str, page: str
) -> None:
    """Real records: Wiktextract appends the template's g= label."""
    lemma_entry = {
        "word": page,
        "lang_code": lang_code,
        "senses": [{"glosses": ["a lemma"]}],
    }
    form_entry = {
        "word": form,
        "lang_code": lang_code,
        "senses": [{"tags": ["form-of"], "form_of": [{"word": cited}]}],
    }

    items = list(normalize([form_entry, lemma_entry]))

    assert _inflection_keys(items) == [((lang_code, page), (lang_code, form))]


def test_label_letters_inside_a_word_are_kept() -> None:
    """A lemma ending in "pf" is not read as the label " pf"."""
    lemma_entry = {
        "word": "Kam",
        "lang_code": "de",
        "senses": [{"glosses": ["a lemma"]}],
    }
    form_entry = {
        "word": "Kampfes",
        "lang_code": "de",
        "senses": [{"tags": ["form-of"], "form_of": [{"word": "Kampf"}]}],
    }

    items = list(normalize([form_entry, lemma_entry]))

    assert _inflection_keys(items) == []


def test_normalize_drops_inflection_edge_when_the_lemma_has_no_page() -> None:
    """A form whose lemma has no page of its own gets no edge.

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


def test_alt_form_edge_kept_when_main_form_has_no_page() -> None:
    """A variant links to its main spelling even when that is a redlink."""
    variant_entry = {
        "word": "hemo-",
        "lang_code": "en",
        "senses": [
            {
                "tags": ["US", "alt-of", "morpheme", "standard"],
                "alt_of": [{"word": "haemo-"}],
            },
        ],
    }

    edges = [
        item
        for item in normalize([variant_entry])
        if isinstance(item, EtymEdge)
    ]

    assert [(e.rel_type, e.src.headword) for e in edges] == [
        (RelType.ALT_FORM, "haemo-")
    ]


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
    lemma_entry = {
        "word": "avvertire",
        "lang_code": "it",
        "senses": [{"glosses": ["to warn"]}],
    }

    items = list(normalize([entry, lemma_entry]))

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


def test_normalize_drops_an_edge_from_a_term_to_itself() -> None:
    """A cross-reference to another section of the same word is no edge.

    Real record: pt "matreira" (noun) carries {{bor+|pt|kea|matrêra}} (a
    real ancestor, Kabuverdianu) alongside {{der|pt|pt|matreira|pos=etymology
    1}}: Wiktionary's cross-reference to a different etymology section of
    the *same* headword. Tree nodes are terms, so the edge would make a
    node its own parent.
    """
    entry = {
        "word": "matreira",
        "lang_code": "pt",
        "pos": "noun",
        "etymology_templates": [
            {"name": "bor+", "args": {"1": "pt", "2": "kea", "3": "matrêra"}},
            {
                "name": "der",
                "args": {
                    "1": "pt",
                    "2": "pt",
                    "3": "matreira",
                    "pos": "etymology 1",
                },
            },
        ],
    }

    edges = [i for i in normalize([entry]) if isinstance(i, EtymEdge)]

    assert [edge.src.key for edge in edges] == [("kea", "matrêra")]


def test_normalize_logs_dropped_self_loops_by_kind(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A dropped self-loop is counted, so lost variety ancestry shows.

    Real record: lmo "de" ({{inh|lmo|lmo-old|de}}) inherits from Old
    Lombard "de", which files under Lombard and so is the same node.
    """
    variety = {
        "word": "de",
        "lang_code": "lmo",
        "etymology_templates": [
            {"name": "inh", "args": {"1": "lmo", "2": "lmo-old", "3": "de"}},
        ],
    }
    section = {
        "word": "matreira",
        "lang_code": "pt",
        "etymology_number": "2",
        "etymology_templates": [
            {"name": "der", "args": {"1": "pt", "2": "pt", "3": "matreira"}},
        ],
    }
    same_term = _entry_with({"name": "m", "args": {"1": "en", "2": "x"}})
    inflection = {
        "word": "can",
        "lang_code": "gd",
        "senses": [{"tags": ["form-of"], "form_of": [{"word": "can"}]}],
    }

    with caplog.at_level(logging.INFO):
        items = list(normalize([variety, section, same_term, inflection]))

    assert not any(isinstance(item, EtymEdge) for item in items)
    assert "dropped self-loop edges (4)" in caplog.text
    assert "variety (1)" in caplog.text
    assert "section (1)" in caplog.text
    assert "same term (1)" in caplog.text
    assert "inflection (1)" in caplog.text


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
