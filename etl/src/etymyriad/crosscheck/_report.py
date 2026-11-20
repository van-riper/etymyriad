"""Choose the dump entries whose pages render an etymology tree."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from etymyriad.normalize import WiktextractEntry


def tree_headwords(
    entries: Iterable[WiktextractEntry],
) -> Iterator[tuple[str, str]]:
    """Yield each entry whose etymon call sets `tree=1`.

    Args:
        entries: Decoded Wiktextract entries.

    Yields:
        The (headword, language code) of each such entry, once per pair.
    """
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        if any(
            call.name == "etymon" and call.args.get("tree") == "1"
            for call in entry.etymology_templates
        ):
            key = (entry.word, entry.lang_code)
            if key not in seen:
                seen.add(key)
                yield key


def headwords_by_language(
    headwords: Iterable[tuple[str, str]],
    lang_codes: Sequence[str],
    limit: int,
) -> dict[str, list[str]]:
    """Take up to `limit` headwords for each chosen language.

    Args:
        headwords: (headword, language code) pairs, as `tree_headwords`
            yields them.
        lang_codes: The languages to sample.
        limit: The most headwords to take per language.

    Returns:
        Each chosen language mapped to its headwords in input order; a
        language with none maps to an empty list.
    """
    sample: dict[str, list[str]] = {code: [] for code in lang_codes}
    for headword, lang_code in headwords:
        taken = sample.get(lang_code)
        if taken is None or len(taken) >= limit:
            continue
        taken.append(headword)
        if all(len(chosen) >= limit for chosen in sample.values()):
            break
    return sample
