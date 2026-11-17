"""Map raw Wiktextract entries to graph objects.

Each Wiktextract entry describes one word and carries `etymology_templates`:
structured records of the {{inh}}, {{bor}}, {{der}}, ... templates used on the
page. We translate those into directed `EtymEdge`s (ancestor -> the entry's own
term).
"""

from etymyriad.normalize._edges import TEMPLATE_REL_TYPES
from etymyriad.normalize._nodes import referenced_term_key, term_of_entry
from etymyriad.normalize._normalize import normalize
from etymyriad.normalize._sections import section_claims
from etymyriad.normalize._wiktextract import WiktextractEntry, field_paths

__all__ = [
    "TEMPLATE_REL_TYPES",
    "WiktextractEntry",
    "field_paths",
    "normalize",
    "referenced_term_key",
    "section_claims",
    "term_of_entry",
]
