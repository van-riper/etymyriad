"""Bridge Wiktionary language codes and ISO 639 for the ETL."""

from __future__ import annotations

from etymyriad.languages._aliases import SHORTHAND_ALIASES
from etymyriad.languages._membership import filter_in_scope, is_in_scope
from etymyriad.languages._model import Language, LanguageKind, LanguageSet
from etymyriad.languages._registry import (
    SNAPSHOT_PATH,
    canonical_code,
    default_registry,
    get_language_set,
    is_reconstructed_code,
    resolve_language,
    split_variety,
)
from etymyriad.languages._sources import USER_AGENT, sync_snapshot

__all__ = [
    "SHORTHAND_ALIASES",
    "SNAPSHOT_PATH",
    "USER_AGENT",
    "Language",
    "LanguageKind",
    "LanguageSet",
    "canonical_code",
    "default_registry",
    "filter_in_scope",
    "get_language_set",
    "is_in_scope",
    "is_reconstructed_code",
    "resolve_language",
    "split_variety",
    "sync_snapshot",
]
