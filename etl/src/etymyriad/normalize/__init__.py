"""Map raw Wiktextract entries to graph objects.

Each Wiktextract entry describes one word and carries `etymology_templates`:
structured records of the {{inh}}, {{bor}}, {{der}}, ... templates used on the
page. We translate those into directed `EtymEdge`s (ancestor -> the entry's own
lexeme).
"""

from __future__ import annotations

from etymyriad.normalize._edges import TEMPLATE_REL_TYPES
from etymyriad.normalize._lexemes import lexeme_of_entry
from etymyriad.normalize._normalize import normalize

__all__ = ["TEMPLATE_REL_TYPES", "lexeme_of_entry", "normalize"]
