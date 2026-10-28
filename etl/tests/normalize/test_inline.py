"""Tests for parsing the <ety:...> chains nested in etymon terms."""

from __future__ import annotations

from etymyriad.normalize._inline import InlineRelation, inline_relations


def test_term_without_a_chain_has_no_relations() -> None:
    """An id annotation alone states no further ancestry."""
    assert inline_relations("*h₂ey-<id:life>", "ine-pro") == []


def test_chain_yields_one_relation_per_hop() -> None:
    """Real record: en "merchant", enm:marchaunt then Anglo-Norman, Latin."""
    raw = "enm:marchaunt<ety:bor<xno:marchaunt<ety:der<la:mercāns>>>>"

    assert inline_relations(raw, "en") == [
        InlineRelation("xno", "marchaunt", "enm", "marchaunt", "bor", None),
        InlineRelation("la", "mercāns", "xno", "marchaunt", "der", None),
    ]


def test_unprefixed_child_takes_its_parents_language() -> None:
    """Real record: en "because", enm:bi cause<ety:af<by><cause>>."""
    raw = "enm:bi cause<ety:af<by><cause>>"

    assert inline_relations(raw, "en") == [
        InlineRelation("enm", "by", "enm", "bi cause", "af", 1),
        InlineRelation("enm", "cause", "enm", "bi cause", "af", 2),
    ]


def test_unprefixed_top_level_term_takes_the_default_language() -> None:
    """Real record: en "a-", ar-<ety:inh<gmw-pro:*uʀ->>."""
    raw = "ar-<ety:inh<gmw-pro:*uʀ->>"

    assert inline_relations(raw, "enm") == [
        InlineRelation("gmw-pro", "*uʀ-", "enm", "ar-", "inh", None),
    ]


def test_modifiers_before_the_chain_are_ignored() -> None:
    """Real record: gmh "ab", gmh:ab<id:of><ety:inh<goh:ab<id:of>>>."""
    raw = "gmh:ab<id:of><ety:inh<goh:ab<id:of>>>"

    assert inline_relations(raw, "en") == [
        InlineRelation("goh", "ab", "gmh", "ab", "inh", None),
    ]


def test_term_written_only_as_alt_names_the_descendant() -> None:
    """Real record: la "aria", la:<alt:āērea><ety:from<āēr>>."""
    raw = "la:<alt:āērea><ety:from<āēr>>"

    assert inline_relations(raw, "en") == [
        InlineRelation("la", "āēr", "la", "āērea", "from", None),
    ]


def test_term_with_neither_text_nor_alt_has_no_relations() -> None:
    """Real record: en "October", enm:<ety:bor<fro:octobre>>."""
    assert inline_relations("enm:<ety:bor<fro:octobre>>", "en") == []


def test_affix_chain_nested_inside_another_chain() -> None:
    """Real record: itc-pro "domaō", with an :af hop inside an :inh hop."""
    raw = (
        "itc-pro:*domaō<ety:inh<ine-pro:<alt:*domh₂éyeti>"
        "<ety:af<*demh₂-><*-éyeti>>>>"
    )

    assert inline_relations(raw, "en") == [
        InlineRelation(
            "ine-pro", "*domh₂éyeti", "itc-pro", "*domaō", "inh", None
        ),
        InlineRelation("ine-pro", "*demh₂-", "ine-pro", "*domh₂éyeti", "af", 1),
        InlineRelation("ine-pro", "*-éyeti", "ine-pro", "*domh₂éyeti", "af", 2),
    ]


def test_modifier_text_with_commas_does_not_split_the_term() -> None:
    """Real record: en "gab", enm:gab<ety:der<non:gabba<alt:gabb><t:...>>>."""
    raw = "enm:gab<ety:der<non:gabba<alt:gabb><t:jest, mockery>>>"

    assert inline_relations(raw, "en") == [
        InlineRelation("non", "gabba", "enm", "gab", "der", None),
    ]


def test_uncertain_modifier_child_is_not_a_term() -> None:
    """Real record: en "dag", enm:dagge<ety:bor<fro:dague><unc:1>>."""
    raw = "enm:dagge<ety:bor<fro:dague><unc:1>>"

    assert inline_relations(raw, "en") == [
        InlineRelation("fro", "dague", "enm", "dagge", "bor", None),
    ]


def test_literal_gloss_modifier_child_is_not_a_term() -> None:
    """Real record: pt "kumquat", a <lit:...> child after the source."""
    raw = "pt:kumquat<ety:bor<yue:gam1 gwat1><lit:golden tangerine>>"

    assert inline_relations(raw, "pt") == [
        InlineRelation("yue", "gam1 gwat1", "pt", "kumquat", "bor", None),
    ]


def test_dash_placeholder_child_is_not_a_term() -> None:
    """Real record: pt "Gerardo", a "-" term with only a language."""
    assert inline_relations("pt:Gerardo<ety:bor<ger:->>", "pt") == []


def test_language_code_that_matches_a_modifier_stays_a_term() -> None:
    """Indonesian "id" and Turkish "tr" are languages, not modifiers."""
    raw = "en:foo<ety:bor<id:bar><tr:baz>>"

    assert inline_relations(raw, "en") == [
        InlineRelation("id", "bar", "en", "foo", "bor", 1),
        InlineRelation("tr", "baz", "en", "foo", "bor", 2),
    ]
