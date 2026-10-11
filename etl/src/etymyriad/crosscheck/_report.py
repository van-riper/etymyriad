"""Choose the dump entries whose pages render an etymology tree."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


def tree_headwords(
    entries: Iterable[Mapping[str, Any]],
) -> Iterator[tuple[str, str]]:
    """Yield each entry whose etymon call sets `tree=1`.

    Args:
        entries: Parsed Wiktextract entries.

    Yields:
        The (headword, language code) of each such entry, once per pair.
    """
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        calls = entry.get("etymology_templates") or []
        if any(
            call["name"] == "etymon" and call["args"].get("tree") == "1"
            for call in calls
        ):
            key = (entry["word"], entry["lang_code"])
            if key not in seen:
                seen.add(key)
                yield key
