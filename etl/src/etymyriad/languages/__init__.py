"""Language metadata: name/family lookups and v1-scope filtering."""

from __future__ import annotations

from etymyriad.languages.membership import (
    filter_indo_european,
    is_indo_european,
)
from etymyriad.languages.names import language_name

__all__ = ["filter_indo_european", "is_indo_european", "language_name"]
