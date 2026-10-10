"""Tests for the graph model invariants."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from etymyriad.model import (
    REL_TYPE_LABELS,
    EtymEdge,
    RelType,
    Term,
)

_SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def test_term_rejects_out_of_range_section() -> None:
    """A section outside SMALLINT range is rejected."""
    with pytest.raises(ValueError, match="section"):
        Term("en", "bank", section=-1)
    with pytest.raises(ValueError, match="section"):
        Term("en", "bank", section=40_000)


def test_term_key_ignores_section_and_variety() -> None:
    """Node identity is the (lang_code, headword) pair alone."""
    plain = Term("la", "aqua")
    cited = Term("la", "aqua", section=2, variety_code="la-lat")
    assert plain.key == cited.key == ("la", "aqua")


def test_edge_requires_an_anchor() -> None:
    """An edge with no anchor is rejected (every edge is cited)."""
    with pytest.raises(ValueError, match="anchor"):
        EtymEdge(Term("la", "aqua"), Term("en", "aqua"), RelType.BORROWED)


def test_reltype_values_mirror_sql_enum() -> None:
    """RelType's members must match edge_type in db/schema.sql exactly."""
    schema = _SCHEMA.read_text()
    enum_body = re.search(
        r"CREATE TYPE edge_type AS ENUM \((.*?)\);", schema, re.DOTALL
    )
    assert enum_body is not None, "edge_type enum not found in schema.sql"
    sql_values = set(re.findall(r"'(\w+)'", enum_body.group(1)))

    assert {member.value for member in RelType} == sql_values


def test_rel_type_labels_cover_every_rel_type() -> None:
    """Every RelType has an (abbreviation, full name) pair defined."""
    assert set(REL_TYPE_LABELS) == set(RelType)


def test_rel_type_labels_are_nonempty_and_distinct() -> None:
    """Abbreviations are non-empty and unique per relation type."""
    abbreviations = [label.abbreviation for label in REL_TYPE_LABELS.values()]
    assert all(abbreviations)
    assert len(abbreviations) == len(set(abbreviations))


def test_rel_types_match_what_normalize_can_emit() -> None:
    """RelType lists exactly the relation types normalize can emit."""
    assert [rel.value for rel in RelType] == [
        "inherited",
        "borrowed",
        "learned_borrowing",
        "semi_learned_borrowing",
        "derived",
        "root",
        "affix",
        "compound",
        "calque",
        "mention",
        "surface_analysis",
        "inflection",
    ]
