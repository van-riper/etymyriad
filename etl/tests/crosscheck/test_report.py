"""Tests for choosing which dump entries carry an etymology tree."""

from __future__ import annotations

from etymyriad.crosscheck import tree_headwords


def _entry(
    word: str, lang_code: str, *calls: dict[str, str]
) -> dict[str, object]:
    return {
        "word": word,
        "lang_code": lang_code,
        "etymology_templates": [
            {"name": "etymon", "args": args} for args in calls
        ],
    }


def test_entry_with_a_tree_flag_is_selected() -> None:
    """`tree=1` on an etymon call marks an entry that has a tree."""
    entries = [_entry("wine", "en", {"1": "en", "2": ":inh", "tree": "1"})]
    assert list(tree_headwords(entries)) == [("wine", "en")]


def test_entry_without_a_tree_flag_is_skipped() -> None:
    """An etymon call with no `tree` renders no tree."""
    entries = [_entry("wine", "en", {"1": "en", "2": ":inh"})]
    assert list(tree_headwords(entries)) == []


def test_other_template_with_a_tree_arg_is_skipped() -> None:
    """Only the etymon template renders a tree."""
    entries = [
        {
            "word": "x",
            "lang_code": "en",
            "etymology_templates": [{"name": "inh", "args": {"tree": "1"}}],
        }
    ]
    assert list(tree_headwords(entries)) == []


def test_headword_repeats_once_per_entry() -> None:
    """Each entry yields once even with several tree calls."""
    call = {"1": "en", "2": ":inh", "tree": "1"}
    entries = [_entry("wine", "en", call, call)]
    assert list(tree_headwords(entries)) == [("wine", "en")]
