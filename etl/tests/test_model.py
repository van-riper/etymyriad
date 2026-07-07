"""Tests for the graph model invariants."""

from __future__ import annotations

import pytest

from etymyriad.model import EtymEdge, Lexeme, RelType


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
