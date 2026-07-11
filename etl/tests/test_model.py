"""Tests for the graph model invariants."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from etymyriad.model import EtymEdge, Lexeme, RelType

_SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def test_lexeme_requires_source_ref() -> None:
    """A lexeme with an empty source_ref is rejected (nothing is unsourced)."""
    with pytest.raises(ValueError, match="source_ref"):
        Lexeme(lang_code="en", headword="water", source_ref="")


def test_edge_requires_source_ref() -> None:
    """An edge with an empty source_ref is rejected (every edge is cited)."""
    src = Lexeme(lang_code="ine-pro", headword="ph₂tḗr", source_ref="w:x")
    dst = Lexeme(lang_code="en", headword="father", source_ref="w:y")
    with pytest.raises(ValueError, match="source_ref"):
        EtymEdge(src=src, dst=dst, rel_type=RelType.INHERITED, source_ref="")


def test_lexeme_dedup_in_set() -> None:
    """Two Lexemes with identical fields collapse to one set member."""
    a = Lexeme(lang_code="en", headword="water", source_ref="w:x")
    b = Lexeme(lang_code="en", headword="water", source_ref="w:x")
    c = Lexeme(lang_code="en", headword="fire", source_ref="w:x")
    assert {a, b, c} == {a, c}


def test_edge_dedup_in_set() -> None:
    """Two EtymEdges with identical fields collapse to one set member."""
    src = Lexeme(lang_code="ine-pro", headword="ph₂tḗr", source_ref="w:x")
    dst = Lexeme(lang_code="en", headword="father", source_ref="w:y")
    other = Lexeme(lang_code="de", headword="Vater", source_ref="w:y")
    a = EtymEdge(src=src, dst=dst, rel_type=RelType.INHERITED, source_ref="w:z")
    b = EtymEdge(src=src, dst=dst, rel_type=RelType.INHERITED, source_ref="w:z")
    c = EtymEdge(
        src=src, dst=other, rel_type=RelType.INHERITED, source_ref="w:z"
    )
    assert {a, b, c} == {a, c}


def test_reltype_values_mirror_sql_enum() -> None:
    """RelType's members must match etym_rel_type in db/schema.sql exactly."""
    schema = _SCHEMA.read_text()
    enum_body = re.search(
        r"CREATE TYPE etym_rel_type AS ENUM \((.*?)\);", schema, re.DOTALL
    )
    assert enum_body is not None, "etym_rel_type enum not found in schema.sql"
    sql_values = set(re.findall(r"'(\w+)'", enum_body.group(1)))

    assert {member.value for member in RelType} == sql_values
