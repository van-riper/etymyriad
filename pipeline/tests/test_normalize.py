"""Tests for the normalization layer."""

from __future__ import annotations

from etymyriad.model import RelType
from etymyriad.normalize import TEMPLATE_RELS, lexeme_of_entry


def test_template_map_covers_core_relations() -> None:
    """The template map resolves the core relation abbreviations."""
    assert TEMPLATE_RELS["inh"] is RelType.INHERITED
    assert TEMPLATE_RELS["bor"] is RelType.BORROWED
    assert TEMPLATE_RELS["der"] is RelType.DERIVED


def test_reconstructed_headword_is_flagged() -> None:
    """A leading-asterisk headword is flagged as reconstructed."""
    entry = {"word": "*wréh₂ds", "lang_code": "ine-pro", "pos": "root"}
    lexeme = lexeme_of_entry(entry)
    assert lexeme.is_reconstructed is True
    assert lexeme.lang_code == "ine-pro"


def test_plain_headword_is_not_reconstructed() -> None:
    """A plain headword is not flagged as reconstructed."""
    entry = {"word": "water", "lang_code": "en", "pos": "noun"}
    lexeme = lexeme_of_entry(entry)
    assert lexeme.is_reconstructed is False
