"""Narrow the combined Wiktextract dump to Indo-European entries.

kaikki.org publishes one dump for every language Wiktionary describes;
`filter_indo_european` cuts it down to this project's v1 scope before
`parse` or `normalize` ever see it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.languages._registry import (
    indo_european_branch,
    resolve_language,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


def is_indo_european(entry: Mapping[str, object]) -> bool:
    """Whether an entry's language falls under Indo-European.

    Args:
        entry: A parsed Wiktextract entry.

    Returns:
        True if entry["lang_code"] resolves to a language whose
        Wiktionary lineage starts at "ine".
    """
    code = entry.get("lang_code")
    if not isinstance(code, str):
        return False
    language = resolve_language(code)
    return language is not None and indo_european_branch(language) is not None


def filter_indo_european(
    entries: Iterable[Mapping[str, object]],
) -> Iterator[Mapping[str, object]]:
    """Yield only entries whose language is Indo-European.

    Args:
        entries: Parsed Wiktextract entries, any language.

    Yields:
        Entries that pass `is_indo_european`.
    """
    for entry in entries:
        if is_indo_european(entry):
            yield entry
