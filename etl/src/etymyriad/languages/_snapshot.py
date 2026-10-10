"""The committed registry snapshot's shape, and how sync builds it."""

from __future__ import annotations

from typing import NotRequired, TypedDict


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
