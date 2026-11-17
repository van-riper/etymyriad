"""Bridge Wiktionary language codes and ISO 639 for the ETL."""

from etymyriad.languages._aliases import SHORTHAND_ALIASES
from etymyriad.languages._membership import is_in_scope
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
from etymyriad.languages._sources import sync_snapshot

__all__ = [
    "SHORTHAND_ALIASES",
    "SNAPSHOT_PATH",
    "Language",
    "LanguageKind",
    "LanguageSet",
    "canonical_code",
    "default_registry",
    "get_language_set",
    "is_in_scope",
    "is_reconstructed_code",
    "resolve_language",
    "split_variety",
    "sync_snapshot",
]
