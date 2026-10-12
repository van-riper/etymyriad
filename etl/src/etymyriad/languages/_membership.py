"""Narrow the combined Wiktextract dump to the language families in scope.

kaikki.org publishes one dump for every language Wiktionary describes;
`filter_in_scope` cuts it down to this project's scope before `parse` or
`normalize` ever see it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.config import SCOPE_FAMILIES
from etymyriad.languages._registry import resolve_language

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


def is_in_scope(entry: Mapping[str, object]) -> bool:
    """Whether an entry's language falls under a family in scope.

    Args:
        entry: A parsed Wiktextract entry.

    Returns:
        True if entry["lang_code"] resolves to a language whose
        Wiktionary lineage starts at a code in `SCOPE_FAMILIES`.
    """
    code = entry.get("lang_code")
    if not isinstance(code, str):
        return False
    # Wiktionary prefixes custom codes with their family, so a code the
    # snapshot lost ("ine-grp-pro") still names its family up front.
    language = resolve_language(code) or resolve_language(code.split("-", 1)[0])
    if language is None or language.language_set is None:
        return False
    return language.language_set.path[0] in SCOPE_FAMILIES


def filter_in_scope(
    entries: Iterable[Mapping[str, object]],
) -> Iterator[Mapping[str, object]]:
    """Yield only entries whose language is in scope.

    Args:
        entries: Parsed Wiktextract entries, any language.

    Yields:
        Entries that pass `is_in_scope`.
    """
    for entry in entries:
        if is_in_scope(entry):
            yield entry
