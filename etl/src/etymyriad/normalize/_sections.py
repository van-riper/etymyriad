"""Read the claims an "Etymology N" section states about its links."""

from typing import TYPE_CHECKING

from etymyriad.model import SectionClaim, Term
from etymyriad.normalize._nodes import _referenced_term

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from etymyriad.normalize._wiktextract import (
        WiktextractEntry,
        _WiktextractLinkedTerm,
    )


def section_claims(entry: WiktextractEntry) -> Iterator[SectionClaim]:
    """Yield the ids and listed terms an entry's numbered section states.

    An unnumbered entry is its page's only etymology, so nothing needs
    to tell its sections apart and it yields nothing.

    Args:
        entry: A decoded Wiktextract entry.

    Yields:
        One claim per declared id, per term the section lists under
        Descendants (at any depth) or Derived terms, and per Hanja a
        Korean syllable section glosses.
    """
    if entry.section == 0:
        return
    lang_code, headword = _referenced_term(entry.lang_code, entry.word).key
    page = Term(lang_code, headword, section=entry.section)

    for wiktionary_id in _declared_ids(entry):
        yield SectionClaim(page, wiktionary_id=wiktionary_id)
    for listed in _descendants(entry.descendants):
        yield SectionClaim(page, listed=listed)
    for derived in entry.derived:
        if derived.word:
            listed = _referenced_term(entry.lang_code, derived.word)
            yield SectionClaim(page, listed=listed)
    for reading in _hanja_readings(entry):
        yield SectionClaim(page, reading=reading)


def _hanja_readings(entry: WiktextractEntry) -> Iterator[str]:
    """Yield each Hanja a Korean syllable section glosses.

    A syllable's sense glosses one Hanja it is the reading of, as
    "麻: hemp; sesame" or a bare "瑪", after the rendered reading table
    Wiktextract puts first.

    Yields:
        Each single-character gloss prefix, in sense order.
    """
    if entry.lang_code != "ko" or entry.pos != "syllable":
        return
    for sense in entry.senses:
        if not sense.glosses:
            continue
        hanja = sense.glosses[-1].split(":", 1)[0].strip()
        # A gloss that is only the table header names no Hanja.
        if len(hanja) == 1:
            yield hanja


def _declared_ids(entry: WiktextractEntry) -> Iterator[str]:
    """Yield each id the section's templates and senses declare.

    Yields:
        Each non-empty id from {{etymid}}, {{etymon|id=}}, and
        {{senseid}}, with the sense id's language prefix removed.
    """
    for template in entry.etymology_templates:
        if template.name == "etymid":
            raw = template.args.get("2", "")
        elif template.name == "etymon":
            raw = template.args.get("id", "")
        else:
            continue
        if raw.strip():
            yield raw.strip()
    prefix = f"{entry.lang_code}:"
    for sense in entry.senses:
        for raw in sense.senseid:
            wiktionary_id = raw.removeprefix(prefix).strip()
            if wiktionary_id:
                yield wiktionary_id


def _descendants(items: Iterable[_WiktextractLinkedTerm]) -> Iterator[Term]:
    """Yield every term a nested Descendants list names, depth first.

    Yields:
        Each named term, as a template reference to it would key it.
    """
    for item in items:
        if item.lang_code and item.word:
            yield _referenced_term(item.lang_code, item.word)
        yield from _descendants(item.descendants)
