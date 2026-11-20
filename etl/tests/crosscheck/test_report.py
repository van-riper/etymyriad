"""Tests for choosing which dump entries carry an etymology tree."""

import msgspec

from etymyriad.crosscheck import headwords_by_language, tree_headwords
from etymyriad.normalize import WiktextractEntry


def _entry(
    word: str, lang_code: str, *calls: dict[str, str]
) -> WiktextractEntry:
    return msgspec.convert(
        {
            "word": word,
            "lang_code": lang_code,
            "etymology_templates": [
                {"name": "etymon", "args": args} for args in calls
            ],
        },
        WiktextractEntry,
    )


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
    entry = {
        "word": "x",
        "lang_code": "en",
        "etymology_templates": [{"name": "inh", "args": {"tree": "1"}}],
    }
    entries = [msgspec.convert(entry, WiktextractEntry)]
    assert list(tree_headwords(entries)) == []


def test_headword_repeats_once_per_entry() -> None:
    """Each entry yields once even with several tree calls."""
    call = {"1": "en", "2": ":inh", "tree": "1"}
    entries = [_entry("wine", "en", call, call)]
    assert list(tree_headwords(entries)) == [("wine", "en")]


def test_headword_with_several_entries_is_yielded_once() -> None:
    """Entries share one page, so a headword needs one fetch."""
    call = {"1": "en", "2": ":inh", "tree": "1"}
    entries = [_entry("free", "en", call), _entry("free", "en", call)]
    assert list(tree_headwords(entries)) == [("free", "en")]


def test_sample_takes_up_to_the_limit_per_language() -> None:
    """Each chosen language gets its own quota, in dump order."""
    headwords = [
        ("cat", "en"),
        ("kitab", "ar"),
        ("dog", "en"),
        ("qalam", "ar"),
        ("bab", "ar"),
    ]
    assert headwords_by_language(headwords, ["ar", "en"], 2) == {
        "ar": ["kitab", "qalam"],
        "en": ["cat", "dog"],
    }


def test_sample_skips_unchosen_languages() -> None:
    """Only the chosen languages are sampled."""
    headwords = [("cat", "en"), ("kitab", "ar")]
    assert headwords_by_language(headwords, ["ar"], 5) == {"ar": ["kitab"]}


def test_sample_keeps_a_language_with_no_trees() -> None:
    """A chosen language with no trees maps to an empty list."""
    headwords = [("cat", "en")]
    assert headwords_by_language(headwords, ["zh"], 5) == {"zh": []}


def test_sample_stops_reading_once_every_quota_is_full() -> None:
    """The dump is long, so reading ends when no language needs more."""
    headwords = iter([("cat", "en"), ("dog", "en"), ("fox", "en")])
    headwords_by_language(headwords, ["en"], 1)
    assert next(headwords) == ("dog", "en")
