"""The committed registry snapshot's shape, and how sync builds it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple, NotRequired, TypedDict

if TYPE_CHECKING:
    from collections.abc import Mapping


class FamilyRecord(TypedDict):
    """One Wiktionary family, as stored in the snapshot."""

    name: str
    parent: NotRequired[str]
    proto_language: NotRequired[str]
    wikidata_qid: NotRequired[int]
    iso639_5: NotRequired[str]


class LanguageRecord(TypedDict):
    """One Wiktionary full language, as stored in the snapshot."""

    name: str
    type: str
    family: NotRequired[str]
    wikidata_qid: NotRequired[int]
    scripts: NotRequired[list[str]]
    wikimedia_codes: NotRequired[list[str]]
    iso639_1: NotRequired[str]
    iso639_2b: NotRequired[str]
    iso639_3: NotRequired[str]


class VarietyRecord(TypedDict):
    """One Wiktionary etymology-only variety, as stored in the snapshot."""

    name: str
    parent: str
    wikidata_qid: NotRequired[int]


class Snapshot(TypedDict):
    """Every Wiktionary code the registry knows, keyed by code."""

    sources: dict[str, str]
    families: dict[str, FamilyRecord]
    languages: dict[str, LanguageRecord]
    varieties: dict[str, VarietyRecord]


type RawRecords = Mapping[str, Mapping[str, Any]]


class WiktionaryExports(NamedTuple):
    """Module:JSON data's three exports, keyed by Wiktionary code.

    Attributes:
        languages: export_languages, restricted to the keys sync asks for.
        families: export_families.
        varieties: export_etymology_languages.
    """

    languages: RawRecords
    families: RawRecords
    varieties: RawRecords


@dataclass(frozen=True, slots=True)
class WikidataIso:
    """ISO 639 codes Wikidata states, from best-rank statements only.

    Attributes:
        iso639_3_by_item: P220 values per Wikidata item number.
        iso639_1_by_item: P218 values per item.
        iso639_2_by_item: P219 values per item (both B and T forms).
        iso639_5_codes: Every P1798 value.
    """

    iso639_3_by_item: Mapping[int, frozenset[str]]
    iso639_1_by_item: Mapping[int, frozenset[str]]
    iso639_2_by_item: Mapping[int, frozenset[str]]
    iso639_5_codes: frozenset[str]


def _split(field: str | None) -> list[str]:
    return [part for part in (field or "").split(",") if part]


def _only(codes: frozenset[str]) -> str | None:
    return next(iter(codes)) if len(codes) == 1 else None


def _add_iso_codes(
    record: LanguageRecord,
    code: str,
    wikidata: WikidataIso,
    all_iso639_3: frozenset[str],
) -> None:
    """Join one Wiktionary code to its ISO codes, by code alone.

    A Wiktionary QID often names a broader or different item than the
    language (e.g. "mkh-mvi" points at Vietnamese), so the QID is never
    used to pick a code.
    """
    if len(code) == 3:
        if code in all_iso639_3:
            record["iso639_3"] = code
        return

    items = [
        item
        for item, codes in wikidata.iso639_1_by_item.items()
        if code in codes
    ]
    if len(code) != 2 or len(items) != 1:
        return

    record["iso639_1"] = code
    iso639_3 = wikidata.iso639_3_by_item.get(items[0], frozenset())
    if (terminological := _only(iso639_3)) is not None:
        record["iso639_3"] = terminological
    iso639_2 = wikidata.iso639_2_by_item.get(items[0], frozenset())
    if (bibliographic := _only(iso639_2 - iso639_3)) is not None:
        record["iso639_2b"] = bibliographic


def _language_record(
    code: str,
    raw: Mapping[str, Any],
    wikidata: WikidataIso,
    all_iso639_3: frozenset[str],
) -> LanguageRecord:
    record: LanguageRecord = {"name": raw["1"], "type": raw["type"]}
    if family := raw.get("3"):
        record["family"] = family
    if qid := raw.get("2"):
        record["wikidata_qid"] = qid
    if scripts := _split(raw.get("4")):
        record["scripts"] = scripts
    if wikimedia_codes := _split(raw.get("wikimedia_codes")):
        record["wikimedia_codes"] = wikimedia_codes
    _add_iso_codes(record, code, wikidata, all_iso639_3)
    return record


def _family_record(
    code: str,
    raw: Mapping[str, Any],
    wikidata: WikidataIso,
    language_codes: frozenset[str],
) -> FamilyRecord:
    record: FamilyRecord = {"name": raw["1"]}
    # "qfa-not" (not a family) names itself as parent to mark a root.
    if (parent := raw.get("3")) and parent != code:
        record["parent"] = parent
    conventional_proto = f"{code}-pro"
    if proto := raw.get("protoLanguage"):
        record["proto_language"] = proto
    elif conventional_proto in language_codes:
        record["proto_language"] = conventional_proto
    if qid := raw.get("2"):
        record["wikidata_qid"] = qid
    if code in wikidata.iso639_5_codes:
        record["iso639_5"] = code
    return record


def _variety_record(raw: Mapping[str, Any]) -> VarietyRecord:
    record: VarietyRecord = {"name": raw["1"], "parent": raw["parent"]}
    if qid := raw.get("2"):
        record["wikidata_qid"] = qid
    return record


def build_snapshot(
    wiktionary: WiktionaryExports,
    wikidata: WikidataIso,
    sources: Mapping[str, str],
) -> Snapshot:
    """Join Wiktionary's language data with Wikidata's ISO 639 codes.

    Args:
        wiktionary: The three Module:JSON data exports.
        wikidata: ISO 639 codes per Wikidata item.
        sources: Attribution and fetch-date notes, stored verbatim.

    Returns:
        The snapshot the registry loads.
    """
    language_codes = frozenset(wiktionary.languages) | frozenset(
        wiktionary.varieties
    )
    all_iso639_3 = frozenset().union(*wikidata.iso639_3_by_item.values())
    return {
        "sources": dict(sources),
        "families": {
            code: _family_record(code, raw, wikidata, language_codes)
            for code, raw in wiktionary.families.items()
        },
        "languages": {
            code: _language_record(code, raw, wikidata, all_iso639_3)
            for code, raw in wiktionary.languages.items()
        },
        "varieties": {
            code: _variety_record(raw)
            for code, raw in wiktionary.varieties.items()
        },
    }
