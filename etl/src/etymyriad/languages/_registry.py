"""Link a snapshot into languages and sets, and resolve raw codes."""

from __future__ import annotations

import functools
import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from etymyriad.languages._aliases import DRIFT_ALIASES, SHORTHAND_ALIASES
from etymyriad.languages._model import Language, LanguageKind, LanguageSet
from etymyriad.model import PROTO_LANG_SUFFIX

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from etymyriad.languages._model import LanguageCode, SetCode
    from etymyriad.languages._snapshot import LanguageRecord, Snapshot

SNAPSHOT_PATH = Path(__file__).with_name("registry.json")
_INDO_EUROPEAN = "ine"


class Registry:
    """Every Wiktionary code, linked into languages and language sets."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Link every record so each parent pointer is a real object.

        Two records sharing one code, even across kinds or letter case,
        raise ValueError, as does a family or variety that is its own
        ancestor.
        """
        _reject_colliding_codes(snapshot)
        self._sets = _link_sets(snapshot)
        self._languages = _link_languages(snapshot, self._sets)
        self._codes_by_casefold = {
            code.casefold(): code for code in self._languages
        }

    def get_set(self, code: SetCode) -> LanguageSet | None:
        """Return the set with exactly this code, if any."""
        return self._sets.get(code)

    def get(self, code: LanguageCode) -> Language | None:
        """Return the language with exactly this code, if any."""
        return self._languages.get(code)

    def resolve(self, raw_code: str) -> Language | None:
        """Resolve a raw dump or template code to its canonical language.

        Returns:
            The language, or None for a code the snapshot does not know.
        """
        code = (
            DRIFT_ALIASES.get(raw_code)
            or SHORTHAND_ALIASES.get(raw_code)
            or raw_code
        )
        if (language := self._languages.get(code)) is not None:
            return language
        folded = self._codes_by_casefold.get(code.casefold())
        # Case slips only in subtags ("en-us"); a base code in the wrong
        # case ("NL" for "NL.") is junk, not Dutch.
        if folded is None or folded.split("-")[0] != code.split("-")[0]:
            return None
        return self._languages[folded]


def _reject_colliding_codes(snapshot: Snapshot) -> None:
    codes = Counter(
        code.casefold()
        for section in ("families", "languages", "varieties")
        for code in snapshot[section]
    )
    if clashes := sorted(code for code, count in codes.items() if count > 1):
        msg = f"codes collide across kinds or case: {clashes}"
        raise ValueError(msg)


def _link_parents_first[T](
    codes: Iterable[str],
    parent_of: Callable[[str], str | None],
    make: Callable[[str, T | None], T],
    linked: dict[str, T],
) -> None:
    """Build each code after its parent, so pointers exist at construction.

    Codes already in `linked` count as built, so a variety can hang off
    a full language linked earlier. A code that is its own ancestor
    raises ValueError.
    """

    def link(code: str, pending: frozenset[str]) -> T:
        if code in linked:
            return linked[code]
        if code in pending:
            msg = f"cycle through code {code!r}"
            raise ValueError(msg)
        parent_code = parent_of(code)
        parent = link(parent_code, pending | {code}) if parent_code else None
        linked[code] = make(code, parent)
        return linked[code]

    for code in codes:
        link(code, frozenset())


def _link_sets(snapshot: Snapshot) -> dict[SetCode, LanguageSet]:
    families = snapshot["families"]
    linked: dict[SetCode, LanguageSet] = {}

    def make(code: SetCode, superset: LanguageSet | None) -> LanguageSet:
        record = families[code]
        return LanguageSet(
            code=code,
            name=record["name"],
            superset=superset,
            proto_language_code=record.get("proto_language"),
            wikidata_qid=record.get("wikidata_qid"),
            iso639_5=record.get("iso639_5"),
        )

    _link_parents_first(
        families, lambda code: families[code].get("parent"), make, linked
    )
    return linked


def _full_language(
    code: LanguageCode,
    record: LanguageRecord,
    sets: Mapping[SetCode, LanguageSet],
) -> Language:
    family = record.get("family")
    kind = LanguageKind(record["type"])
    return Language(
        code=code,
        name=record["name"],
        kind=kind,
        language_set=sets[family] if family else None,
        is_reconstructed=kind is LanguageKind.RECONSTRUCTED,
        wikidata_qid=record.get("wikidata_qid"),
        scripts=tuple(record.get("scripts", ())),
        wikimedia_codes=tuple(record.get("wikimedia_codes", ())),
        iso639_1=record.get("iso639_1"),
        iso639_2b=record.get("iso639_2b"),
        iso639_3=record.get("iso639_3"),
    )


def _is_reconstructed_variety(code: LanguageCode, name: str) -> bool:
    # Variety records carry no type, and the suffix alone misleads:
    # "oc-pro" is Provençal, an attested variety.
    return code.endswith(PROTO_LANG_SUFFIX) and name.startswith("Proto-")


def _link_languages(
    snapshot: Snapshot, sets: Mapping[SetCode, LanguageSet]
) -> dict[LanguageCode, Language]:
    linked = {
        code: _full_language(code, record, sets)
        for code, record in snapshot["languages"].items()
    }
    linked |= {
        code: Language(
            code=code,
            name=language_set.name,
            kind=LanguageKind.COLLECTIVE,
            language_set=language_set,
            wikidata_qid=language_set.wikidata_qid,
        )
        for code, language_set in sets.items()
    }
    varieties = snapshot["varieties"]

    def make(code: LanguageCode, parent: Language | None) -> Language:
        record = varieties[code]
        return Language(
            code=code,
            name=record["name"],
            kind=LanguageKind.VARIETY,
            language_set=parent.language_set if parent is not None else None,
            parent=parent,
            is_reconstructed=_is_reconstructed_variety(code, record["name"]),
            wikidata_qid=record.get("wikidata_qid"),
        )

    _link_parents_first(
        varieties, lambda code: varieties[code]["parent"], make, linked
    )
    return linked


@functools.cache
def default_registry() -> Registry:
    """Load the committed snapshot once per process.

    Returns:
        The registry linked from the committed snapshot.
    """
    return Registry(json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")))


def resolve_language(raw_code: str) -> Language | None:
    """Resolve a raw code against the committed snapshot.

    Returns:
        The canonical language, or None for an unknown code.
    """
    return default_registry().resolve(raw_code)


def get_language_set(code: SetCode) -> LanguageSet | None:
    """Return the committed snapshot's set with exactly this code."""
    return default_registry().get_set(code)


def canonical_code(raw_code: str) -> LanguageCode:
    """Return the canonical code, or `raw_code` when it is unknown."""
    language = resolve_language(raw_code)
    return raw_code if language is None else language.code


def is_reconstructed_code(raw_code: str) -> bool:
    """Whether a code names a reconstructed language.

    Returns:
        The registry's flag, or for a code the snapshot does not know,
        whether it follows Wiktionary's "-pro" naming convention.
    """
    language = resolve_language(raw_code)
    if language is None:
        return raw_code.endswith(PROTO_LANG_SUFFIX)
    return language.is_reconstructed


def indo_european_branch(language: Language) -> str | None:
    """Name the top-level Indo-European branch a language falls under.

    Returns:
        The name of the set directly under "ine" on the language's path
        (e.g. "Germanic" for English), "Indo-European" for a language
        filed under "ine" itself, or None outside Indo-European.
    """
    if language.language_set is None:
        return None
    lineage = language.language_set.lineage
    if lineage[0].code != _INDO_EUROPEAN:
        return None
    return lineage[1].name if len(lineage) > 1 else lineage[0].name
